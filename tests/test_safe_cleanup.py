import json
import pytest
from book_to_skill.workdir import create_owned_workdir, cleanup_workdir

def metadata(path, token):
    target = path / 'metadata.json'
    target.write_text(json.dumps({'workdir': str(path), 'cleanup_token': token}))
    return target

def test_owned_cleanup_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr('tempfile.gettempdir', lambda: str(tmp_path))
    first, second = tmp_path / 'book_skill_work-first', tmp_path / 'book_skill_work-second'
    token = create_owned_workdir(first)
    create_owned_workdir(second)
    cleanup_workdir(metadata(first, token))
    assert not first.exists()
    assert second.exists()

def test_refuse_unmarked_and_external(tmp_path, monkeypatch):
    monkeypatch.setattr('tempfile.gettempdir', lambda: str(tmp_path))
    for target in [tmp_path, tmp_path / 'user', tmp_path / 'book_skill_work-unmarked']:
        target.mkdir(exist_ok=True)
        meta = metadata(target, 'invalid')
        with pytest.raises(ValueError):
            cleanup_workdir(meta)
        assert target.exists()

def test_failure_retained(tmp_path, monkeypatch):
    monkeypatch.setattr('tempfile.gettempdir', lambda: str(tmp_path))
    target = tmp_path / 'book_skill_work-failed'
    create_owned_workdir(target)
    with pytest.raises((ValueError, FileNotFoundError)):
        cleanup_workdir(target / 'metadata.json')
    assert target.exists()

def test_metadata_cannot_redirect(tmp_path, monkeypatch):
    monkeypatch.setattr('tempfile.gettempdir', lambda: str(tmp_path))
    first, second = tmp_path / 'book_skill_work-first', tmp_path / 'book_skill_work-second'
    token = create_owned_workdir(first)
    create_owned_workdir(second)
    meta = metadata(first, token)
    meta.write_text(json.dumps({'workdir': str(second), 'cleanup_token': token}))
    with pytest.raises(ValueError):
        cleanup_workdir(meta)
    assert first.exists() and second.exists()

def test_symlink_refused(tmp_path, monkeypatch):
    monkeypatch.setattr('tempfile.gettempdir', lambda: str(tmp_path))
    target = tmp_path / 'book_skill_work-target'
    token = create_owned_workdir(target)
    meta = metadata(target, token)
    link = tmp_path / 'book_skill_work-link'
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip('Creating symlinks is unavailable on this Windows account')
    with pytest.raises(ValueError):
        cleanup_workdir(link / meta.name)
    assert target.exists()


def test_random_paths_do_not_reuse_same_pid():
    from book_to_skill.config import default_output_dir
    assert default_output_dir() != default_output_dir()


def test_extractor_auto_and_explicit_workdir(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    source = tmp_path / 'synthetic.txt'
    source.write_text('A synthetic chapter. ' * 100, encoding='utf-8')
    env = os.environ.copy()
    env.pop('BOOK_SKILL_WORKDIR', None)
    run = subprocess.run([sys.executable, 'scripts/extract.py', str(source), '--install-missing', 'no'],
                         env=env, stdin=subprocess.DEVNULL, text=True, capture_output=True, encoding='utf-8')
    assert run.returncode == 0, run.stderr
    path = Path(next(line.split('->', 1)[1].strip() for line in run.stdout.splitlines() if 'Workdir ->' in line))
    meta = json.loads((path / 'metadata.json').read_text(encoding='utf-8'))
    assert meta['cleanup_token']
    cleaned = subprocess.run([sys.executable, '-m', 'book_to_skill.workdir', str(path / 'metadata.json')],
                             env=env, stdin=subprocess.DEVNULL, text=True, capture_output=True, encoding='utf-8')
    assert cleaned.returncode == 0, cleaned.stderr
    assert not path.exists()
    explicit = tmp_path / 'user-workdir'
    env['BOOK_SKILL_WORKDIR'] = str(explicit)
    run = subprocess.run([sys.executable, 'scripts/extract.py', str(source), '--install-missing', 'no'],
                         env=env, stdin=subprocess.DEVNULL, text=True, capture_output=True, encoding='utf-8')
    assert run.returncode == 0, run.stderr
    with pytest.raises(ValueError):
        cleanup_workdir(explicit / 'metadata.json')
    assert (explicit / 'full_text.txt').exists()


def test_system_temp_alias_is_canonicalized_without_trusting_candidate_links(tmp_path, monkeypatch):
    from pathlib import Path
    from book_to_skill.config import default_output_dir
    alias = tmp_path.parent / 'system-temp-alias'
    real_resolve, real_is_symlink = Path.resolve, Path.is_symlink
    monkeypatch.setattr('tempfile.gettempdir', lambda: str(alias))
    monkeypatch.setattr(Path, 'resolve', lambda self, **kw: tmp_path if self == alias else real_resolve(self, **kw))
    monkeypatch.setattr(Path, 'is_symlink', lambda self: self == alias or real_is_symlink(self))
    path = default_output_dir()
    assert path.parent == tmp_path
    token = create_owned_workdir(path)
    meta = metadata(path, token)
    with pytest.raises(ValueError, match='linked path'):
        cleanup_workdir(alias / path.name / meta.name)
    assert path.exists()
    cleanup_workdir(meta)
    assert not path.exists()


def test_explicit_output_reconfigured_after_import_is_not_marked_owned(tmp_path, monkeypatch):
    import sys
    from book_to_skill import config, utils
    source = tmp_path / 'synthetic.md'
    source.write_text('Chapter 1\nSynthetic content.\n', encoding='utf-8')
    explicit = tmp_path / 'user-work'
    monkeypatch.setenv('BOOK_SKILL_WORKDIR', str(explicit))
    # Long-lived callers can replace cached output constants after module import.
    for module in (config, utils):
        monkeypatch.setattr(module, 'OUTPUT_DIR', explicit)
        monkeypatch.setattr(module, 'OUTPUT_TEXT', explicit / 'full_text.txt')
        monkeypatch.setattr(module, 'OUTPUT_META', explicit / 'metadata.json')
    monkeypatch.setattr(sys, 'argv', ['extract.py', str(source), '--mode', 'text', '--install-missing', 'no'])
    utils.main()
    meta = json.loads((explicit / 'metadata.json').read_text(encoding='utf-8'))
    assert meta['cleanup_token'] is None
    assert not (explicit / '.book-skill-owner.json').exists()
    assert 'Synthetic content.' in (explicit / 'full_text.txt').read_text(encoding='utf-8')

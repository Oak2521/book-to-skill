"""Ownership-checked cleanup for extractor-created temporary directories."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

MARKER = '.book-skill-owner.json'


def _plain_path(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError(f'Refusing linked path: {part}')
    return path


def _temporary_child(path):
    path = _plain_path(path)
    # The system temp root may legitimately contain aliases (macOS /var).
    # Canonicalize that trusted root; never canonicalize a candidate before its link checks.
    root = Path(tempfile.gettempdir()).resolve()
    if path.resolve().parent != root or not path.name.startswith('book_skill_work-'):
        raise ValueError('Cleanup requires an owned direct child of the temporary directory')
    return path


def create_owned_workdir(path):
    path = _temporary_child(path)
    path.mkdir(mode=0o700, exist_ok=False)
    token = uuid.uuid4().hex
    (path / MARKER).write_text(json.dumps({'path': str(path.resolve()), 'token': token}), encoding='utf-8')
    return token


def cleanup_workdir(metadata_path):
    """Remove only a successful, marked automatic run; preserve user directories."""
    meta_path = _plain_path(metadata_path)
    path = _temporary_child(meta_path.parent)
    if meta_path.name != 'metadata.json':
        raise ValueError('Expected this run\'s metadata.json')
    marker = _plain_path(path / MARKER)
    if not marker.is_file():
        raise ValueError('Directory was not created and marked by the extractor')
    owner = json.loads(marker.read_text(encoding='utf-8'))
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    if (owner.get('path') != str(path.resolve()) or
            meta.get('workdir') != str(path.resolve()) or
            not owner.get('token') or owner['token'] != meta.get('cleanup_token')):
        raise ValueError('Work directory ownership or metadata mismatch')
    # Conservatively retain linked trees, including Windows junctions.
    for base, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            _plain_path(Path(base) / name)
    shutil.rmtree(path)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metadata', help='metadata.json reported by this successful extraction')
    args = parser.parse_args()
    try:
        cleanup_workdir(args.metadata)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Workdir retained: {exc}\n')

import os
import tempfile
import uuid
from pathlib import Path

def default_output_dir() -> Path:
    """Unpredictable per-task path, also unique if a process ID is reused."""
    return Path(tempfile.gettempdir()).resolve() / f"book_skill_work-{os.getpid()}-{uuid.uuid4().hex}"


AUTO_OUTPUT_DIR = not bool(os.environ.get("BOOK_SKILL_WORKDIR"))
OUTPUT_DIR = Path(os.environ.get("BOOK_SKILL_WORKDIR") or default_output_dir())
# Preserve provenance if a long-lived caller later replaces the output constants.
AUTO_OUTPUT_PATH = OUTPUT_DIR if AUTO_OUTPUT_DIR else None
OUTPUT_TEXT = OUTPUT_DIR / "full_text.txt"
OUTPUT_META = OUTPUT_DIR / "metadata.json"

WORDS_PER_TOKEN = 0.75  # approximate (Latin / whitespace-delimited text)
# CJK scripts carry little or no whitespace, so word-splitting under-counts them
# by orders of magnitude. Count CJK codepoints directly against this
# chars-per-token ratio instead (see estimate_tokens in utils.py).
CJK_CHARS_PER_TOKEN = 1.5  # approximate for cl100k-style tokenizers

TEXT_EXTENSIONS = {".txt", ".text", ".md", ".markdown", ".rst", ".adoc", ".asciidoc"}
HTML_EXTENSIONS = {".html", ".htm", ".xhtml"}
CALIBRE_EBOOK_EXTENSIONS = {".mobi", ".azw", ".azw3"}
SUPPORTED_EXTENSIONS = {
    ".pdf", ".epub", ".docx", ".rtf",
    *TEXT_EXTENSIONS,
    *HTML_EXTENSIONS,
    *CALIBRE_EBOOK_EXTENSIONS,
}

PYTHON_DEPENDENCIES = {
    "pdf_inspector": "pdf-inspector>=1.15,<2",
    "docling": "docling",
    "pypdf": "pypdf",
    "pdfminer": "pdfminer.six",
    "ebooklib": "ebooklib",
    "bs4": "beautifulsoup4",
    "docx": "python-docx",
    "striprtf": "striprtf",
    "trafilatura": "trafilatura",
}


def supported_formats_message() -> str:
    return ", ".join(sorted(SUPPORTED_EXTENSIONS))

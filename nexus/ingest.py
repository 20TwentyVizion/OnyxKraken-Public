"""Nexus Intake — file reading, text extraction, dedup detection, auto-filing.

Handles the first piston of the engine: raw input → cleaned text → ready for chunking.
Supports: .txt, .md, .json, .csv, .pdf (text-only), raw strings.
Auto-files ingested content into the Nexus data directory structure.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nexus.models import Thought, IngestResult

_log = logging.getLogger("nexus.ingest")

# Supported file extensions and their extractors
_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".text", ".log", ".rst"}
_JSON_EXTENSIONS = {".json", ".jsonl"}
_CSV_EXTENSIONS = {".csv", ".tsv"}
_CODE_EXTENSIONS = {".py", ".js", ".ts", ".html", ".css", ".yaml", ".yml", ".toml", ".xml"}
_ALL_SUPPORTED = _TEXT_EXTENSIONS | _JSON_EXTENSIONS | _CSV_EXTENSIONS | _CODE_EXTENSIONS


class IntakePipeline:
    """Reads raw input from files or strings and prepares it for chunking.

    Responsibilities:
      - Extract text from various file formats
      - Clean and normalize text
      - Detect file type and source metadata
      - Auto-file originals into the Nexus raw/ directory
      - Content hash for dedup at the file level
    """

    def __init__(self, raw_dir: str = "", auto_file: bool = True):
        self._raw_dir = raw_dir
        self._auto_file = auto_file
        self._processed_hashes: set = set()

        if raw_dir:
            os.makedirs(raw_dir, exist_ok=True)
            self._load_processed_hashes()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_text(self, text: str, source: str = "manual",
                    filename: str = "") -> Optional[Dict]:
        """Ingest raw text string.

        Returns dict with keys: text, source, source_file, content_hash
        or None if empty/duplicate.
        """
        if not text or not text.strip():
            return None

        text = self._clean_text(text)
        content_hash = self._hash_content(text)

        if content_hash in self._processed_hashes:
            _log.info("Duplicate content detected (hash=%s). Skipping.", content_hash[:8])
            return None

        self._processed_hashes.add(content_hash)

        # Auto-file if enabled
        source_file = ""
        if self._auto_file and self._raw_dir and not filename:
            filename = self._generate_filename(text, source)
            source_file = self._save_raw(text, filename)
        elif filename:
            source_file = filename

        return {
            "text": text,
            "source": source,
            "source_file": source_file,
            "content_hash": content_hash,
        }

    def ingest_file(self, file_path: str) -> Optional[Dict]:
        """Ingest a file by path.

        Extracts text, detects source type, and optionally copies to raw/.
        Returns dict with keys: text, source, source_file, content_hash
        or None if unsupported/empty/duplicate.
        """
        path = Path(file_path)
        if not path.exists():
            _log.warning("File not found: %s", file_path)
            return None

        ext = path.suffix.lower()
        source = f"file:{path.name}"

        # Extract text based on file type
        text = self._extract_text(path, ext)
        if not text or not text.strip():
            _log.info("No text extracted from %s", file_path)
            return None

        text = self._clean_text(text)
        content_hash = self._hash_content(text)

        if content_hash in self._processed_hashes:
            _log.info("Duplicate file content (hash=%s): %s", content_hash[:8], path.name)
            return None

        self._processed_hashes.add(content_hash)

        # Auto-file: copy original to raw/
        source_file = str(path)
        if self._auto_file and self._raw_dir:
            dest = self._auto_file_path(path)
            if dest and str(path.resolve()) != str(Path(dest).resolve()):
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copy2(str(path), dest)
                    source_file = dest
                    _log.info("Filed %s → %s", path.name, dest)
                except (IOError, OSError) as e:
                    _log.debug("Auto-file failed: %s", e)

        return {
            "text": text,
            "source": source,
            "source_file": source_file,
            "content_hash": content_hash,
        }

    def ingest_directory(self, dir_path: str, recursive: bool = True) -> List[Dict]:
        """Ingest all supported files from a directory.

        Returns list of ingest dicts (same format as ingest_file).
        """
        results = []
        path = Path(dir_path)
        if not path.is_dir():
            _log.warning("Not a directory: %s", dir_path)
            return results

        pattern = "**/*" if recursive else "*"
        for file_path in sorted(path.glob(pattern)):
            if file_path.is_file() and file_path.suffix.lower() in _ALL_SUPPORTED:
                result = self.ingest_file(str(file_path))
                if result:
                    results.append(result)

        _log.info("Ingested %d files from %s", len(results), dir_path)
        return results

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    def _extract_text(self, path: Path, ext: str) -> str:
        """Extract text content from a file based on its extension."""
        if ext in _TEXT_EXTENSIONS | _CODE_EXTENSIONS:
            return self._read_text_file(path)

        if ext in _JSON_EXTENSIONS:
            return self._extract_json(path)

        if ext in _CSV_EXTENSIONS:
            return self._extract_csv(path)

        if ext == ".pdf":
            return self._extract_pdf(path)

        _log.debug("Unsupported file type: %s", ext)
        return ""

    @staticmethod
    def _read_text_file(path: Path) -> str:
        """Read a plain text file."""
        encodings = ["utf-8", "utf-16", "latin-1", "cp1252"]
        for enc in encodings:
            try:
                return path.read_text(encoding=enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
        return ""

    @staticmethod
    def _extract_json(path: Path) -> str:
        """Extract text from JSON — concatenate all string values."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            texts = []

            def _walk(obj):
                if isinstance(obj, str) and len(obj) > 5:
                    texts.append(obj)
                elif isinstance(obj, dict):
                    for v in obj.values():
                        _walk(v)
                elif isinstance(obj, list):
                    for item in obj:
                        _walk(item)

            _walk(data)
            return "\n\n".join(texts)
        except (json.JSONDecodeError, IOError) as e:
            _log.debug("JSON extract failed: %s", e)
            return ""

    @staticmethod
    def _extract_csv(path: Path) -> str:
        """Extract text from CSV — join all cells."""
        try:
            import csv
            rows = []
            with open(path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                for row in reader:
                    row_text = " | ".join(cell.strip() for cell in row if cell.strip())
                    if row_text:
                        rows.append(row_text)
            return "\n".join(rows)
        except Exception as e:
            _log.debug("CSV extract failed: %s", e)
            return ""

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        """Extract text from PDF (requires PyPDF2 or pdfplumber)."""
        # Try PyPDF2 first
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(p for p in pages if p.strip())
        except ImportError:
            pass
        except Exception as e:
            _log.debug("PyPDF2 extraction failed: %s", e)

        # Try pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
                return "\n\n".join(p for p in pages if p.strip())
        except ImportError:
            _log.info("No PDF library available (install PyPDF2 or pdfplumber)")
        except Exception as e:
            _log.debug("pdfplumber extraction failed: %s", e)

        return ""

    # ------------------------------------------------------------------
    # Auto-filing
    # ------------------------------------------------------------------

    def _auto_file_path(self, source_path: Path) -> str:
        """Determine where to auto-file a source file in the raw/ directory."""
        if not self._raw_dir:
            return ""

        # Organize by date subfolder
        date_str = time.strftime("%Y-%m-%d")
        dest_dir = os.path.join(self._raw_dir, date_str)
        dest = os.path.join(dest_dir, source_path.name)

        # Handle name collisions
        if os.path.exists(dest):
            stem = source_path.stem
            ext = source_path.suffix
            counter = 1
            while os.path.exists(dest):
                dest = os.path.join(dest_dir, f"{stem}_{counter}{ext}")
                counter += 1

        return dest

    def _save_raw(self, text: str, filename: str) -> str:
        """Save raw text to a file in raw/."""
        if not self._raw_dir:
            return ""

        date_str = time.strftime("%Y-%m-%d")
        dest_dir = os.path.join(self._raw_dir, date_str)
        os.makedirs(dest_dir, exist_ok=True)

        dest = os.path.join(dest_dir, filename)
        try:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(text)
            return dest
        except IOError as e:
            _log.warning("Failed to save raw text: %s", e)
            return ""

    @staticmethod
    def _generate_filename(text: str, source: str) -> str:
        """Generate a filename from text content and source."""
        # Use first ~40 chars of text as slug
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", text[:40]).strip("_").lower()
        if not slug:
            slug = "input"
        timestamp = time.strftime("%H%M%S")
        return f"{slug}_{timestamp}.md"

    # ------------------------------------------------------------------
    # Dedup
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_content(text: str) -> str:
        """SHA-256 hash of normalized text content."""
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _load_processed_hashes(self):
        """Load previously processed content hashes from a manifest file."""
        manifest = os.path.join(self._raw_dir, ".manifest.json")
        if os.path.exists(manifest):
            try:
                with open(manifest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._processed_hashes = set(data.get("hashes", []))
            except (json.JSONDecodeError, IOError):
                pass

    def save_manifest(self):
        """Save the processed hashes manifest."""
        if not self._raw_dir:
            return
        manifest = os.path.join(self._raw_dir, ".manifest.json")
        try:
            with open(manifest, "w", encoding="utf-8") as f:
                json.dump({"hashes": list(self._processed_hashes)}, f)
        except IOError as e:
            _log.debug("Manifest save failed: %s", e)

    @property
    def processed_count(self) -> int:
        return len(self._processed_hashes)

    # ------------------------------------------------------------------
    # Text cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalize whitespace, strip control chars."""
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\r", "\n", text)
        # Collapse 3+ newlines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

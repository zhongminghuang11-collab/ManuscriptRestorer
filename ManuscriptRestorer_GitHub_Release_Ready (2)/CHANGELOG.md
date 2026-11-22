# Changelog

## v1.0 — 2026-11-22 (experimental)

- Local Python HTTP service with browser review interface.
- OCR through Tesseract; optional PaddleOCR adapter.
- Candidate detection for some red horizontal strike-through marks.
- Optional local vision-model review suggestions.
- Character-level insert, delete and replace events with collision checks.
- Original/revised draft reconstruction, multi-page input, JSON/TXT export.
- Saved projects and command-line utilities.
- Added explicit known-issues log, documentation, and reproducible tests.

**Not a stable release.** Recognition accuracy on real handwritten manuscripts has not been established.

## Public-open-source preparation — 2026-11-22

- Added MIT license, contribution guidelines, issue/PR templates and CI tests.
- Switched PDF rendering from PyMuPDF to the permissively licensed pypdfium2 binding.
- Preserved explicit experimental status and unresolved recognition limitations.

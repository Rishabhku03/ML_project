# Phase 02 Plan 02-02: TextCleaner Pipeline Module Summary

## One-Liner

Created a configurable, ordered text cleaning pipeline (TextCleaner) implementing Unicode normalization, markdown stripping, URL extraction, emoji standardization, and PII scrubbing for real-time and batch processing paths.

## Tasks Completed

| Task | Name | Status | Key Output |
|------|------|--------|------------|
| 1 | Install dependencies and create TextCleaner module | ✅ Complete | `src/data/text_cleaner.py` |
| 2 | Write unit tests for text_cleaner | ✅ Complete | `tests/test_text_cleaner.py` |

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `src/data/text_cleaner.py` | Created | TextCleaner class + 5 cleaning step functions |
| `tests/test_text_cleaner.py` | Created | 14 unit tests covering all cleaning functions |
| `requirements.txt` | Modified | Added ftfy, emoji, markdownify |
| `pyproject.toml` | Modified | Added ftfy, emoji, markdownify to dependencies |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed markdownify escaping non-HTML markdown markers**
- **Found during:** Task 2 (test execution)
- **Issue:** `markdownify()` escapes Markdown syntax like `**` to `\*\*` when given non-HTML input, causing the regex strip step to leave backslashes in the output (`\\bold\\ text` instead of `bold text`)
- **Fix:** Added unescape step `re.sub(r'\\([*_~`])', r'\1', text)` before the syntax marker strip step
- **Files modified:** `src/data/text_cleaner.py`
- **Impact:** `strip_markdown` now correctly handles both HTML input and raw Markdown input

## Dependencies Installed

| Package | Version | Purpose |
|---------|---------|---------|
| ftfy | 6.3.1 | Unicode normalization (ONLINE-05) |
| emoji | 2.15.0 | Emoji ↔ shortcode conversion (ONLINE-02) |
| markdownify | 1.2.2 | HTML tag stripping (ONLINE-01) |

## Requirements Satisfied

- ONLINE-01: Markdown/HTML stripping ✅
- ONLINE-02: Emoji standardization to :shortcode: ✅
- ONLINE-03: URL extraction with [URL] placeholder ✅
- ONLINE-04: PII scrubbing (email, phone, username) ✅
- ONLINE-05: Unicode normalization via ftfy ✅
- ONLINE-06: Configurable ordered pipeline ✅

## Decisions Applied

| Decision | Description |
|----------|-------------|
| D-05 | Pipeline class design — TextCleaner with configurable ordered steps |
| D-06 | Step execution order: fix_unicode → strip_markdown → extract_urls → standardize_emojis → scrub_pii |
| D-07 | Regex-based PII scrubbing for emails, phone numbers, usernames |
| D-08 | URLs replaced with [URL] placeholder |
| D-09 | Emoji standardization to :shortcode: format |
| D-10 | Module location: src/data/text_cleaner.py |

## Verification Evidence

```
pytest tests/test_text_cleaner.py -x -v
============================== 14 passed in 0.18s ==============================
```

All 14 tests pass:
- `test_fix_unicode` — mojibake fixed
- `test_strip_markdown_html` — HTML tags stripped
- `test_strip_markdown_syntax` — Markdown markers removed
- `test_extract_urls` — single URL replaced
- `test_extract_urls_multiple` — multiple URLs replaced
- `test_standardize_emojis` — emoji → :shortcode:
- `test_standardize_emojis_no_emoji` — plain text unchanged
- `test_scrub_pii_email` — email → [EMAIL]
- `test_scrub_pii_phone` — phone → [PHONE]
- `test_scrub_pii_username` — @mention → [USER]
- `test_text_cleaner_pipeline_order` — full pipeline all elements
- `test_text_cleaner_custom_steps` — custom steps restrict pipeline
- `test_text_cleaner_empty_input` — empty string edge case
- `test_text_cleaner_no_side_effects` — input not mutated

## Known Stubs

None — all functions are fully implemented and tested.

## Self-Check: PASSED

All claimed files verified present on disk.

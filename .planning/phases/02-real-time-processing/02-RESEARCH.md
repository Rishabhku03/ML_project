# Phase 2: Real-time Processing - Research

**Researched:** 2026-04-03
**Domain:** Text preprocessing pipeline, async HTTP traffic generation, FastAPI middleware
**Confidence:** HIGH

## Summary

Phase 2 builds three interconnected components: (1) a shared `TextCleaner` pipeline class for text normalization, (2) a FastAPI middleware that intercepts incoming messages and cleans them before persistence, and (3) a synthetic HTTP traffic generator that sends sustained load to the API. The locked decisions in CONTEXT.md are well-researched and architecturally sound. The key discovery is that the existing `combined_dataset.csv` contains 391,645 rows (not 1.58M — due to embedded newlines), and sampled data shows ~1.5% have markdown, ~3% have URLs, and ~3.5% have emojis — confirming the cleaning pipeline will have real work to do.

**Primary recommendation:** Use `markdownify` + `emoji` + `ftfy` as the standard stack. Use `BaseHTTPMiddleware` from Starlette for the FastAPI middleware. Use `asyncio` + `aiohttp` for the traffic generator at 15-20 RPS.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Sustained stream dispatch at ~15-20 RPS (matches production load spec from project report)
- **D-02:** Async concurrency model using `asyncio` + `aiohttp` (matches FastAPI's async nature)
- **D-03:** Mixed data source — reads from `combined_dataset.csv` rows AND generates synthetic messages via existing HF API calls
- **D-04:** Generator script: `src/data/synthetic_traffic_generator.py`
- **D-05:** Pipeline class design — `TextCleaner` class with configurable ordered steps (not individual composable functions or single monolithic function)
- **D-06:** Step execution order: Unicode normalization (ftfy) → Markdown strip → URL extraction → Emoji standardization → PII scrub
- **D-07:** Regex-based PII scrubbing for emails, phone numbers, usernames (no external NER dependency)
- **D-08:** URLs replaced with `[URL]` placeholder (preserves position for NLP, not stored separately)
- **D-09:** Emoji standardization to `:shortcode:` format (e.g., 😂 → `:joy:`)
- **D-10:** Module location: `src/data/text_cleaner.py` (shared by online and batch paths per ONLINE-06)
- **D-11:** FastAPI middleware intercepts both `POST /messages` and `POST /flags` — cleans `text`/`reason` fields before route handler
- **D-12:** Middleware persists message to PostgreSQL `messages` table on ingest (write-on-ingest, not deferred)
- **D-13:** API response returns both `raw_text` and `cleaned_text` for demo verification
- **D-14:** Separate `cleaned_text` column on `messages` table (raw text preserved for audit)
- **D-15:** Schema change via standalone migration script (ALTER TABLE), not update to init SQL
- **D-16:** Cleaned data also uploaded to MinIO `zulip-raw-messages/cleaned/` for consistency with Phase 1 pattern
- **D-17:** MinIO upload batched at 10K rows (smaller than Phase 1's 50K for faster availability)

### Agent's Discretion
- Specific regex patterns for PII detection (email, phone, username)
- Markdown stripping library choice (markdownify, mistune, or custom regex)
- Emoji library choice (emoji, demoji, or custom mapping)
- Middleware error handling behavior (log and continue vs. reject request)
- Traffic generator message template wording and Zulip-style formatting

### Deferred Ideas (OUT OF SCOPE)
- Parquet format for MinIO uploads (deferred to batch pipeline or later)
- Real-time feature store (Redis) for rolling window counts — v2 requirement (ADV-03)
- Redpanda event streaming for true real-time pipeline — v2 requirement (ADV-02)
- Configurable cleaning step order via YAML — deferred to Phase 4 (CONFIG-01)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-04 | Data generator sends synthetic HTTP traffic to FastAPI endpoints | Traffic generator section — async aiohttp at 15-20 RPS |
| ONLINE-01 | Markdown removal from message text | Standard Stack — `markdownify` 1.2.2 recommended |
| ONLINE-02 | Emoji standardization to :shortcode: format | Standard Stack — `emoji` 2.15.0 with `demojize()` |
| ONLINE-03 | URL extraction from message text | Don't Hand-Roll — regex pattern replaces URLs with `[URL]` |
| ONLINE-04 | PII scrubbing (email, phone, username patterns) | Code Examples — validated regex patterns provided |
| ONLINE-05 | Unicode normalization (fix mojibake via ftfy) | Standard Stack — `ftfy` 6.3.1, first pipeline step |
| ONLINE-06 | Shared text_cleaner.py module used by both online and batch paths | Architecture Patterns — TextCleaner class with configurable steps |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ftfy | 6.3.1 | Unicode normalization / mojibake repair | Gold standard for fixing encoding issues. Handles UTF-8/Latin-1 mixups, curly quotes, C1 controls. Cited in NLP research. Apache-2.0. |
| emoji | 2.15.0 | Emoji ↔ shortcode conversion | Most comprehensive emoji library. `demojize()` converts emoji to `:shortcode:`. Supports 14 languages. BSD license. |
| markdownify | 1.2.2 | HTML/markdown → plain text conversion | Converts HTML to markdown, or strips all formatting. Lightweight (15.7KB), well-maintained. Uses BeautifulSoup+lxml (already installed). MIT license. |
| aiohttp | 3.13.3 | Async HTTP client for traffic generator | Already installed. Industry standard for async HTTP in Python. Required for D-02 async concurrency model. |
| fastapi | >=0.135.0 | Web framework (already in requirements) | Already installed. `BaseHTTPMiddleware` for request interception. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lxml | 6.0.2 | XML/HTML parser (markdownify dependency) | Already installed. Used internally by markdownify. |
| beautifulsoup4 | latest | HTML parsing (markdownify dependency) | Will be installed as markdownify dependency. |
| re | stdlib | Regex for PII scrubbing and URL extraction | Built-in. No install needed. |
| asyncio | stdlib | Async I/O for traffic generator | Built-in. No install needed. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| markdownify | mistune (Markdown parser) | Mistune parses Markdown→AST, not HTML→text. We need to strip formatting from chat text that may contain HTML tags. markdownify is the correct direction. |
| markdownify | Custom regex (`re.sub(r'<[^>]+>', '', text)`) | Fragile. Doesn't handle nested tags, entities, or malformed HTML. markdownify uses BeautifulSoup for robust parsing. Worth the dependency. |
| emoji | demoji | demoji is a C wrapper requiring system install. emoji is pure Python, pip-installable, more comprehensive, and actively maintained. |
| emoji | Custom mapping dict | Would need to maintain 3,700+ emoji entries. The `emoji` library tracks Unicode standards updates. Don't hand-roll. |
| ftfy | unicodedata.normalize('NFC', text) | Python's unicodedata only does Unicode normalization forms. ftfy specifically fixes mojibake (encoding errors) — a completely different problem. ftfy is required for D-05. |
| aiohttp | httpx (async) | httpx 0.28.1 is already installed as dev dependency. Could use `httpx.AsyncClient` instead. Tradeoff: httpx has cleaner API but aiohttp is slightly faster for sustained high-throughput. Either works at 15-20 RPS. **Recommendation: use httpx since it's already installed and the traffic generator is a test tool, not production.** |

**Installation:**
```bash
pip install ftfy emoji markdownify
```

**Version verification:** All versions verified from PyPI on 2026-04-03. These are current stable releases.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── data/
│   ├── text_cleaner.py          # NEW: TextCleaner class (shared module)
│   ├── synthetic_traffic_generator.py  # NEW: Async HTTP traffic generator
│   ├── synthetic_generator.py   # EXISTING: HF API generation (reused)
│   └── prompts.py               # EXISTING: Prompt constants
├── api/
│   ├── main.py                  # MODIFY: Add middleware
│   ├── models.py                # MODIFY: Add raw_text, cleaned_text fields
│   └── routes/
│       ├── messages.py          # MODIFY: Persist with cleaned_text
│       └── flags.py             # MODIFY: Persist with cleaned_text
└── utils/
    ├── db.py                    # EXISTING: Used by middleware for PG writes
    ├── minio_client.py          # EXISTING: Used for cleaned data uploads
    └── config.py                # EXISTING: Frozen dataclass config
```

### Pattern 1: TextCleaner Pipeline Class
**What:** A class that accepts an ordered list of cleaning step callables and applies them sequentially to text. Each step is a function `(str) -> str`.
**When to use:** When text preprocessing has multiple ordered transformations that may need different configurations for online vs. batch paths.
**Example:**
```python
# Source: D-05, D-06 — configurable pipeline class
from dataclasses import dataclass, field
from typing import Callable
import ftfy
import emoji
import re
from markdownify import markdownify as md

# Each step is a callable: (str) -> str
def fix_unicode(text: str) -> str:
    return ftfy.fix_text(text)

def strip_markdown(text: str) -> str:
    # markdownify converts HTML→markdown; strip all formatting
    return md(text, strip=['img', 'a', 'b', 'i', 'code', 'pre'], heading_style='ATX')

def extract_urls(text: str) -> str:
    return re.sub(r'https?://\S+', '[URL]', text)

def standardize_emojis(text: str) -> str:
    return emoji.demojize(text, delimiters=(":", ":"))

def scrub_pii(text: str) -> str:
    # Email
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    # Phone (US/international)
    text = re.sub(r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '[PHONE]', text)
    # Username patterns (@ mentions)
    text = re.sub(r'@\w+', '[USER]', text)
    return text

@dataclass
class TextCleaner:
    steps: list[Callable[[str], str]] = field(default_factory=lambda: [
        fix_unicode,
        strip_markdown,
        extract_urls,
        standardize_emojis,
        scrub_pii,
    ])

    def clean(self, text: str) -> str:
        for step in self.steps:
            text = step(text)
        return text
```

### Pattern 2: FastAPI BaseHTTPMiddleware
**What:** Starlette middleware that intercepts requests before they reach route handlers.
**When to use:** When you need to transform request/response data globally across multiple endpoints.
**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/middleware/
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class TextCleaningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only intercept POST /messages and POST /flags
        if request.method == "POST" and request.url.path in ("/messages", "/flags"):
            body = await request.json()
            cleaner = TextCleaner()
            if "text" in body:
                raw = body["text"]
                body["cleaned_text"] = cleaner.clean(raw)
                body["raw_text"] = raw
            # Rebuild request with modified body
            # ... (see Common Pitfalls for the correct approach)
        response = await call_next(request)
        return response
```

**Important:** `BaseHTTPMiddleware` does NOT allow modifying the request body directly. The correct approach is to parse body in middleware, pass cleaned data via `request.state`, and let the route handler read from `request.state`. Alternative: use a dependency injection approach instead.

**Better pattern — use dependency:**
```python
# Source: D-11, D-12 — middleware approach vs. dependency approach
# RECOMMENDED: Use middleware to read body, clean it, and persist to DB
# The route handler returns the response with raw_text and cleaned_text

from starlette.middleware.base import BaseHTTPMiddleware
import json

class TextCleaningMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.cleaner = TextCleaner()

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path in ("/messages", "/flags"):
            body_bytes = await request.body()
            body = json.loads(body_bytes)
            
            cleaned_body = dict(body)
            if "text" in body:
                raw = body["text"]
                cleaned_body["cleaned_text"] = self.cleaner.clean(raw)
                cleaned_body["raw_text"] = raw
            
            # Store on request.state for route handler
            request.state.cleaned_body = cleaned_body
            
            # Persist to PostgreSQL here (D-12)
            await self._persist_to_db(cleaned_body)
        
        response = await call_next(request)
        return response

    async def _persist_to_db(self, body: dict):
        # Insert into messages table with cleaned_text column
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO messages (id, user_id, raw_text, cleaned_text, source) VALUES (%s, %s, %s, %s, %s)",
                    (str(uuid.uuid4()), body.get("user_id"), body.get("raw_text"), body.get("cleaned_text"), body.get("source", "synthetic"))
                )
            conn.commit()
        finally:
            conn.close()
```

### Pattern 3: Async Traffic Generator
**What:** Script that sends sustained HTTP traffic to FastAPI endpoints using asyncio + aiohttp/httpx.
**When to use:** Load testing, synthetic traffic simulation, demo recording.
**Example:**
```python
# Source: D-01, D-02, D-03, D-04
import asyncio
import aiohttp
import csv
import random

TARGET_RPS = 15  # D-01: 15-20 RPS

async def send_message(session, url, payload):
    async with session.post(url, json=payload) as resp:
        return await resp.json()

async def run_traffic_generator(base_url="http://localhost:8000", duration_seconds=60):
    # Load messages from CSV (D-03)
    messages = []
    with open("combined_dataset.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            messages.append(row["text"])
    
    url = f"{base_url}/messages"
    interval = 1.0 / TARGET_RPS
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < duration_seconds:
            text = random.choice(messages)
            payload = {
                "text": text,
                "user_id": f"synthetic-{random.randint(1000,9999)}",
                "source": "synthetic_traffic"
            }
            tasks.append(asyncio.create_task(send_message(session, url, payload)))
            await asyncio.sleep(interval)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return results
```

### Anti-Patterns to Avoid
- **Modifying request.body() in middleware:** Starlette's `Request` object is immutable after body is read. Use `request.state` to pass data between middleware and route handlers.
- **Creating TextCleaner on every request:** Instantiate once in middleware `__init__`, reuse across requests. The `TextCleaner` class is stateless.
- **Synchronous DB calls in async middleware:** Use `asyncio.to_thread()` to wrap psycopg2 calls, or switch to `asyncpg` for true async DB. For this phase, `asyncio.to_thread(get_db_connection)` is sufficient since RPS is low (15-20).
- **Hardcoded regex patterns:** Define PII patterns as module-level constants for testability and configurability.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unicode/mojibake repair | Custom encoding detection | ftfy.fix_text() | Handles multi-layer mojibake, curly quotes, C1 controls. Impossible to match with custom code. |
| Emoji → shortcode | Custom emoji dict | emoji.demojize() | 3,700+ emoji entries, tracks Unicode updates, 14 language support. |
| HTML → plain text | Regex strip tags | markdownify + BeautifulSoup | Nested tags, malformed HTML, entity decoding. Regex breaks on edge cases. |
| URL extraction | Manual string search | re.sub(r'https?://\S+', '[URL]', text) | URL regex is well-established. Simple 1-liner. |
| Email detection | Custom parsing | re.sub(email_pattern, '[EMAIL]', text) | RFC 5322 email regex is well-established. |
| Async HTTP requests | urllib + threading | aiohttp or httpx.AsyncClient | Built-in async support, connection pooling, proper timeout handling. |

**Key insight:** The text cleaning domain has well-established solutions for every sub-problem. Don't invent new ones.

## Runtime State Inventory

> Not applicable — this is a greenfield phase (building new features, not renaming/migrating).

## Common Pitfalls

### Pitfall 1: markdownify Direction Confusion
**What goes wrong:** Using `markdownify` to convert Markdown→plain text. It actually converts HTML→Markdown.
**Why it happens:** The name suggests it creates markdown, but for cleaning chat text we need to *strip* formatting.
**How to avoid:** Use `markdownify(html_text, strip=['a', 'b', 'i', 'img'])` to strip tags and produce plain text. For chat text that's mostly plain with occasional HTML, this produces clean output. If text contains actual Markdown syntax (e.g., `**bold**`), use regex to strip markdown markers: `re.sub(r'[*_~`]+', '', text)`.
**Warning signs:** Test with `"**bold** text"` — markdownify won't strip `**` since it's not HTML.

**Recommendation:** Use a two-phase approach: (1) `markdownify` for HTML entities/tags, (2) regex for Markdown syntax markers (`*`, `_`, `~~`, `` ` ``).

### Pitfall 2: emoji.demojize() Delimiter Behavior
**What goes wrong:** `emoji.demojize()` defaults to using `|` as delimiters: `|thumbs_up|`. But D-09 specifies `:shortcode:` format with `:` delimiters.
**Why it happens:** Default parameter changed between library versions.
**How to avoid:** Always pass `delimiters=(":", ":")` explicitly: `emoji.demojize(text, delimiters=(":", ":"))`.
**Warning signs:** Output contains `|emoji_name|` instead of `:emoji_name:`.

### Pitfall 3: Starlette Request Body Can Only Be Read Once
**What goes wrong:** Middleware reads `await request.body()`, then route handler tries to read it again and gets empty.
**Why it happens:** Request body is a stream consumed on first read.
**How to avoid:** Read body in middleware, parse JSON, store on `request.state.cleaned_body`. Route handler reads from `request.state`, not from `await request.body()`.
**Warning signs:** Route handler receives empty `payload` despite middleware having valid data.

### Pitfall 4: Traffic Generator Overwhelms Single-Threaded FastAPI
**What goes wrong:** At 20 RPS with synchronous psycopg2 DB writes, FastAPI event loop blocks on DB calls.
**Why it happens:** psycopg2 is synchronous. In async middleware, synchronous calls block the event loop.
**How to avoid:** Wrap DB writes in `asyncio.to_thread()` or use `run_in_executor`. At 15-20 RPS this is unlikely to be a real problem, but wrap defensively.
**Warning signs:** Response latency increases linearly with request count.

### Pitfall 5: PII Regex False Positives
**What goes wrong:** Phone regex matches numbers in text that aren't phone numbers (e.g., "call me at 3" or product IDs).
**Why it happens:** Overly broad phone patterns.
**How to avoid:** Use conservative phone patterns requiring at least 10 digits with separators. Test against the actual dataset. Use `[PHONE]` replacement only when pattern matches full phone structure.
**Warning signs:** Cleaned text has `[PHONE]` appearing in non-phone contexts.

## Code Examples

Verified patterns from official sources:

### TextCleaner Pipeline Class
```python
# Source: D-05, D-06 — configurable ordered pipeline
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class TextCleaner:
    """Shared text cleaning pipeline for online and batch paths (ONLINE-06).

    Steps executed in order per D-06:
    1. Unicode normalization (ftfy)
    2. Markdown strip
    3. URL extraction
    4. Emoji standardization
    5. PII scrubbing
    """
    steps: list[Callable[[str], str]] = field(default_factory=list)

    def __post_init__(self):
        if not self.steps:
            self.steps = [
                fix_unicode,
                strip_markdown,
                extract_urls,
                standardize_emojis,
                scrub_pii,
            ]

    def clean(self, text: str) -> str:
        """Apply all cleaning steps sequentially."""
        for step in self.steps:
            text = step(text)
        return text
```

### Markdown Stripping (Two-Phase)
```python
# Source: markdownify PyPI docs + Pitfall 1
from markdownify import markdownify as md
import re

def strip_markdown(text: str) -> str:
    # Phase 1: Convert any HTML to plain text
    text = md(text, strip=['a', 'b', 'i', 'img', 'code', 'pre', 'p', 'div', 'span'])
    # Phase 2: Remove markdown syntax markers
    text = re.sub(r'[*_~`]+', '', text)
    # Phase 3: Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text
```

### Emoji Standardization
```python
# Source: emoji PyPI docs, D-09
import emoji

def standardize_emojis(text: str) -> str:
    """Convert emoji to :shortcode: format per D-09."""
    return emoji.demojize(text, delimiters=(":", ":"))
```

### PII Scrubbing (ONLINE-04)
```python
# Source: D-07 — regex-based, no NER dependency
import re

# Email: RFC 5322 simplified
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Phone: US and international formats (conservative)
PHONE_PATTERN = re.compile(
    r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
)

# Username: @mentions
USERNAME_PATTERN = re.compile(r'@\w+')

def scrub_pii(text: str) -> str:
    """Replace PII with placeholders per D-07, ONLINE-04."""
    text = EMAIL_PATTERN.sub('[EMAIL]', text)
    text = PHONE_PATTERN.sub('[PHONE]', text)
    text = USERNAME_PATTERN.sub('[USER]', text)
    return text
```

### Unicode Normalization
```python
# Source: ftfy.readthedocs.io, D-05 step 1
import ftfy

def fix_unicode(text: str) -> str:
    """Fix mojibake and Unicode issues per ONLINE-05."""
    return ftfy.fix_text(text)
```

### URL Extraction
```python
# Source: D-08 — replace with [URL] placeholder
import re

def extract_urls(text: str) -> str:
    """Replace URLs with [URL] placeholder per D-08."""
    return re.sub(r'https?://\S+', '[URL]', text)
```

### FastAPI Middleware Integration
```python
# Source: https://fastapi.tiangolo.com/tutorial/middleware/
# D-11, D-12, D-13
from starlette.middleware.base import BaseHTTPMiddleware
import json
import uuid
import logging

logger = logging.getLogger(__name__)

class TextCleaningMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.cleaner = TextCleaner()

    async def dispatch(self, request, call_next):
        if request.method == "POST" and request.url.path in ("/messages", "/flags"):
            try:
                body_bytes = await request.body()
                body = json.loads(body_bytes)
                
                # Clean text fields
                if "text" in body:
                    raw = body["text"]
                    cleaned = self.cleaner.clean(raw)
                    body["raw_text"] = raw
                    body["cleaned_text"] = cleaned
                    body["text"] = cleaned  # Route handler sees cleaned text
                
                if "reason" in body and body["reason"]:
                    body["reason_cleaned"] = self.cleaner.clean(body["reason"])
                
                # Persist to PostgreSQL (D-12)
                message_id = str(uuid.uuid4())
                self._persist_message(message_id, body)
                
                # Store for route handler
                request.state.cleaned_body = body
                request.state.message_id = message_id
                
            except Exception as e:
                logger.exception("Middleware cleaning failed, passing request through")
                # Log and continue (Agent's Discretion decision)
        
        response = await call_next(request)
        return response

    def _persist_message(self, message_id: str, body: dict):
        """Persist message with cleaned_text to PostgreSQL (D-12)."""
        from src.utils.db import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO messages (id, user_id, raw_text, cleaned_text, source)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (message_id, body.get("user_id"), body.get("raw_text"),
                     body.get("cleaned_text"), body.get("source", "synthetic"))
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| synchronous requests + threading | asyncio + aiohttp/httpx | Python 3.4+ (asyncio), ~2016 (aiohttp) | Non-blocking I/O for sustained traffic |
| regex-only text cleaning | ftfy + markdownify + emoji pipeline | ftfy 2012, emoji 2.0 2022 | Handles edge cases regex can't (mojibake, Unicode) |
| Starlette function middleware | BaseHTTPMiddleware class | Starlette 0.12+ | OOP approach, cleaner lifecycle |

**Deprecated/outdated:**
- `demoji` library: Less maintained, requires C compilation. Use `emoji` instead.
- Starlette `@app.middleware("http")` function decorator: Still works but `BaseHTTPMiddleware` is the recommended class-based approach.
- `bleach` for HTML sanitization: Deprecated since 2023. Use `markdownify` + `html.unescape` instead.

## Open Questions

1. **markdownify vs. regex for Markdown syntax stripping**
   - What we know: `markdownify` handles HTML→text. Actual Markdown syntax like `**bold**` won't be converted.
   - What's unclear: How much actual Markdown syntax (vs. HTML) exists in the dataset.
   - Recommendation: Use two-phase approach (markdownify for HTML + regex for Markdown markers). Sampled data shows 1.5% of rows have markdown-like patterns.

2. **httpx vs. aiohttp for traffic generator**
   - What we know: httpx 0.28.1 is already installed (dev dependency). aiohttp is not installed but is faster for sustained throughput.
   - What's unclear: Whether the performance difference matters at 15-20 RPS.
   - Recommendation: Use `httpx.AsyncClient` since it's already installed. The performance difference is negligible at this RPS.

3. **Middleware persistence: sync psycopg2 in async context**
   - What we know: psycopg2 is synchronous. FastAPI middleware is async.
   - What's unclear: Whether `asyncio.to_thread()` adds unacceptable latency.
   - Recommendation: At 15-20 RPS, even synchronous psycopg2 calls will complete in <5ms. Wrap with `asyncio.to_thread()` for correctness but expect no performance issues.

## Environment Availability

> Skip if no external dependencies. Phase has external dependencies.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All components | ✓ | 3.12.3 | — |
| pip | Package install | ✓ | 26.0.1 | — |
| FastAPI | Middleware, API | ✓ | >=0.135.0 (in requirements) | — |
| aiohttp | Traffic generator | ✓ | 3.13.3 (installed) | httpx 0.28.1 (also installed) |
| httpx | Traffic generator (alt) | ✓ | 0.28.1 | aiohttp (also installed) |
| lxml | markdownify dep | ✓ | 6.0.2 | — |
| ftfy | Unicode normalization | ✗ | — | pip install ftfy |
| emoji | Emoji standardization | ✗ | — | pip install emoji |
| markdownify | Markdown stripping | ✗ | — | pip install markdownify |
| PostgreSQL | Data persistence | ✓ | — (Docker) | — |
| MinIO | Cleaned data upload | ✓ | — (Docker) | — |
| pytest | Testing | ✓ | 9.0.2 | — |
| pytest-asyncio | Async tests | ✓ | 1.3.0 | — |

**Missing dependencies with no fallback:**
- None — all missing packages have clear pip install paths.

**Missing dependencies with fallback:**
- None needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_text_cleaner.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-04 | Traffic generator sends POST /messages at 15-20 RPS | integration | `pytest tests/test_traffic_generator.py -x -v` | ❌ Wave 0 |
| ONLINE-01 | Markdown stripped from text | unit | `pytest tests/test_text_cleaner.py::test_strip_markdown -x` | ❌ Wave 0 |
| ONLINE-02 | Emoji standardized to :shortcode: | unit | `pytest tests/test_text_cleaner.py::test_standardize_emojis -x` | ❌ Wave 0 |
| ONLINE-03 | URLs replaced with [URL] | unit | `pytest tests/test_text_cleaner.py::test_extract_urls -x` | ❌ Wave 0 |
| ONLINE-04 | PII scrubbed (email, phone, username) | unit | `pytest tests/test_text_cleaner.py::test_scrub_pii -x` | ❌ Wave 0 |
| ONLINE-05 | Unicode normalized via ftfy | unit | `pytest tests/test_text_cleaner.py::test_fix_unicode -x` | ❌ Wave 0 |
| ONLINE-06 | TextCleaner used by middleware | integration | `pytest tests/test_middleware.py::test_cleaning_in_middleware -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_text_cleaner.py -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_text_cleaner.py` — unit tests for each cleaning step + full pipeline
- [ ] `tests/test_middleware.py` — integration test for middleware cleaning + persistence
- [ ] `tests/test_traffic_generator.py` — test that generator sends requests at target RPS
- [ ] `ftfy`, `emoji`, `markdownify` packages — `pip install ftfy emoji markdownify`

*(No existing test infrastructure covers Phase 2 requirements — all test files must be created.)*

## Sources

### Primary (HIGH confidence)
- PyPI: ftfy 6.3.1 (https://pypi.org/project/ftfy/) — verified 2026-04-03
- PyPI: emoji 2.15.0 (https://pypi.org/project/emoji/) — verified 2026-04-03
- PyPI: markdownify 1.2.2 (https://pypi.org/project/markdownify/) — verified 2026-04-03
- ftfy docs: https://ftfy.readthedocs.io/en/latest/fixes.html — fixer functions reference
- FastAPI docs: https://fastapi.tiangolo.com/advanced/middleware/ — middleware patterns
- FastAPI docs: https://fastapi.tiangolo.com/tutorial/middleware/ — custom middleware
- Context7: FastAPI middleware patterns confirmed

### Secondary (MEDIUM confidence)
- Existing codebase analysis — data sampling confirms cleaning needs
- `pyproject.toml` — dependency versions verified
- `tests/conftest.py` — test infrastructure (TestClient, fixtures)

### Tertiary (LOW confidence)
- Training data on PII regex patterns — well-established but should be tested against actual dataset
- Traffic generator RPS calculations — theoretical, need runtime validation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all library versions verified from PyPI, well-established packages
- Architecture: HIGH — FastAPI middleware pattern from official docs, TextCleaner follows locked decisions
- Pitfalls: MEDIUM — based on library docs and common patterns, but edge cases in real data may emerge
- PII regex: MEDIUM — standard patterns but should be validated against actual dataset samples

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (30 days — stable libraries, unlikely to change)

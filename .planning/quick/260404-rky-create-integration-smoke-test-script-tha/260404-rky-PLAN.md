---
phase: quick
plan: "01"
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/smoke_test_integration.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Script exits 0 when all Docker services are reachable"
    - "Script exits non-zero with clear message when a service is down"
    - "TextCleaner pipeline produces cleaned output on sample markdown+emoji+PII input"
    - "Quality gate removes #ERROR! rows and short texts from a test DataFrame"
    - "Temporal leakage filter drops rows where created_at >= decided_at"
    - "Stratified split produces ~70/15/15 proportions on test data"
    - "Versioned snapshot (train/val/test CSVs) appears in MinIO zulip-training-data bucket"
  artifacts:
    - path: "scripts/smoke_test_integration.py"
      provides: "End-to-end integration smoke test for all 3 pipeline phases"
  key_links:
    - from: "scripts/smoke_test_integration.py"
      to: "src.utils.config"
      via: "import config for connection strings"
      pattern: "from src.utils.config import config"
    - from: "scripts/smoke_test_integration.py"
      to: "src.utils.db.get_db_connection"
      via: "PostgreSQL connectivity check"
      pattern: "get_db_connection"
    - from: "scripts/smoke_test_integration.py"
      to: "src.utils.minio_client.get_minio_client"
      via: "MinIO connectivity check"
      pattern: "get_minio_client"
    - from: "scripts/smoke_test_integration.py"
      to: "src.data.text_cleaner.TextCleaner"
      via: "instantiate and call .clean()"
      pattern: "TextCleaner"
    - from: "scripts/smoke_test_integration.py"
      to: "src.data.compile_training_data"
      via: "import and call pipeline functions"
      pattern: "apply_quality_gate"
---

<objective>
Create a single integration smoke test script that validates all 3 pipeline phases end-to-end against live Docker services (PostgreSQL, MinIO).

Purpose: Provide a quick run-command to verify the entire data pipeline is operational after deployment. Catches misconfigurations, broken service connections, and regressions across ingestion, real-time processing, and batch compilation.

Output: `scripts/smoke_test_integration.py`
</objective>

<execution_context>
@/home/kukiku/Desktop/NYU courses/Semester 2/MLOps/Ml_Project/.opencode/get-shit-done/workflows/execute-plan.md
@/home/kukiku/Desktop/NYU courses/Semester 2/MLOps/Ml_Project/.opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

<interfaces>
From src/utils/config.py:
```python
config.DATABASE_URL        # postgresql://user:chatsentry_pg@localhost:5432/chatsentry
config.MINIO_ENDPOINT      # localhost:9000
config.MINIO_ACCESS_KEY    # admin
config.MINIO_SECRET_KEY    # chatsentry_minio
config.BUCKET_RAW          # zulip-raw-messages
config.BUCKET_TRAINING     # zulip-training-data
```

From src/utils/db.py:
```python
def get_db_connection()  # returns psycopg2 connection
```

From src/utils/minio_client.py:
```python
def get_minio_client() -> Minio  # returns Minio client instance
```

From src/data/text_cleaner.py:
```python
class TextCleaner:
    def clean(self, text: str) -> str  # applies 5-step pipeline
```

From src/data/compile_training_data.py:
```python
def apply_quality_gate(df: pd.DataFrame) -> pd.DataFrame
def filter_temporal_leakage(df: pd.DataFrame) -> pd.DataFrame
def select_output_columns(df: pd.DataFrame) -> pd.DataFrame
def stratified_split(df: pd.DataFrame, random_state: int = 42) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
def generate_version() -> str
def upload_snapshot(client, bucket: str, train_df, val_df, test_df) -> str
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create the integration smoke test script</name>
  <files>scripts/smoke_test_integration.py</files>
  <action>
    Create `scripts/smoke_test_integration.py` — a single-file integration smoke test that validates all 3 pipeline phases against live Docker services.

    The script must implement 7 checks in order:
    1. **PostgreSQL reachable** — call `get_db_connection()`, run `SELECT 1`, close connection
    2. **MinIO reachable + buckets exist** — call `get_minio_client()`, verify `config.BUCKET_RAW` and `config.BUCKET_TRAINING` exist
    3. **TextCleaner pipeline** — instantiate `TextCleaner()`, clean a string containing markdown (`**bold**`), URL (`https://example.com`), email (`me@test.org`), and username mention (`@john`), verify each is stripped/replaced
    4. **Quality gate** — call `apply_quality_gate()` on a DataFrame with `#ERROR!` rows and text shorter than 10 chars, verify they are removed
    5. **Temporal leakage filter** — call `filter_temporal_leakage()` on a DataFrame where one row has `created_at >= decided_at`, verify that row is dropped
    6. **Stratified split** — call `stratified_split()` on a 1000-row DataFrame, verify ~70/15/15 proportions and no `label_combo` column in output
    7. **MinIO snapshot upload** — call `upload_snapshot()` with a tiny 2-row DataFrame, then call `client.stat_object()` on each of the 3 split files to verify they exist and are non-empty

    Structure requirements:
    - Use `logging.getLogger("smoke_test")` with `logging.basicConfig(level=INFO)` — NO `print()` statements (per project conventions)
    - Track PASSED/FAILED counts via module-level globals and a `check(name, condition, detail)` helper
    - If PostgreSQL or MinIO checks fail, log a warning and skip downstream checks (phase gate pattern)
    - `main()` function returns `0` on all-pass, `1` on any failure
    - `if __name__ == "__main__"` block calls `sys.exit(main())`
    - Use `import pandas as pd` at module level (needed by quality gate and split checks)
    - Use lazy imports inside check functions for pipeline modules (avoid import-time failures if Docker is down)
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('scripts/smoke_test_integration.py').read()); print('syntax OK')"</automated>
  </verify>
  <done>
    File exists at `scripts/smoke_test_integration.py` with valid Python syntax.
    Contains `main()` function returning 0/1.
    Contains 7 check functions: check_postgres, check_minio, check_text_cleaner, check_quality_gate, check_temporal_leakage, check_stratified_split, check_minio_snapshot.
    Uses `logging` module (no `print()`).
    Phase gates skip downstream checks if Docker services are down.
  </done>
</task>

<task type="auto">
  <name>Task 2: Run smoke test and verify output</name>
  <files>scripts/smoke_test_integration.py</files>
  <action>
    Execute the smoke test script against live Docker services:

    ```bash
    python scripts/smoke_test_integration.py
    ```

    Expected output (with Docker services running):
    ```
    PASS: PostgreSQL reachable
    PASS: MinIO reachable + buckets exist
    PASS: TextCleaner pipeline
    PASS: Quality gate
    PASS: Temporal leakage filter
    PASS: Stratified split
    PASS: MinIO snapshot upload + verification
    Results: 7 passed, 0 failed
    ```

    If services are NOT running, expect:
    ```
    FAIL: PostgreSQL reachable — ...
    FAIL: MinIO reachable + buckets exist — ...
    WARNING: Docker services not fully available — skipping live pipeline checks
    Results: 0 passed, 2 failed
    ```
  </action>
  <verify>
    <automated>python scripts/smoke_test_integration.py</automated>
  </verify>
  <done>
    Script exits 0 with all 7 checks PASS when Docker services are running.
    Script exits 1 with clear FAIL messages when Docker is down.
  </done>
</task>

<task type="auto">
  <name>Task 3: Commit the smoke test script</name>
  <files>scripts/smoke_test_integration.py</files>
  <action>
    ```bash
    git add scripts/smoke_test_integration.py
    git commit -m "feat(quick): add integration smoke test for all 3 pipeline phases"
    ```
  </action>
  <verify>
    <automated>git log -1 --oneline | grep -q "smoke test" && echo "committed"</automated>
  </verify>
  <done>
    Script committed to git with descriptive message.
  </done>
</task>

</tasks>

<verification>
- Run `python -c "import ast; ast.parse(open('scripts/smoke_test_integration.py').read())"` — no syntax errors
- Run `python scripts/smoke_test_integration.py` — all 7 checks pass (with Docker) or clear failure messages (without Docker)
- Verify script uses `logging` module (grep for `print(` should return nothing)
- Verify `main()` function exists and returns int
</verification>

<success_criteria>
- `scripts/smoke_test_integration.py` exists with valid Python syntax
- Script runs successfully against live Docker services (exit 0, all 7 checks PASS)
- Script exits non-zero with clear messages when Docker is down
- All checks implemented: PostgreSQL, MinIO, TextCleaner, quality gate, temporal leakage, stratified split, MinIO snapshot
- Uses `logging` module (no `print()` per project conventions)
- Script committed to git
</success_criteria>

<output>
After completion, create `.planning/quick/260404-rky-create-integration-smoke-test-script-tha/260404-rky-SUMMARY.md`
</output>

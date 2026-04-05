# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ReelForge (影工厂)** is a zero-cost, locally-run AI short video production tool. It enables single developers to generate short videos from scripts, featuring first-frame character locking, AI scene generation, speech synthesis, and video rendering—all without cloud infrastructure costs.

- **Tech Stack**: Streamlit (frontend) + Python 3.10+ (backend) + SQLite (data) + MoviePy/FFmpeg (video)
- **Key Services**: DeepSeek (NLP), 通义万相 (image gen), Edge TTS (speech synthesis)
- **Concurrency Model**: Threading (async/await explicitly forbidden)

---

## Architecture Overview

The codebase is in early development following a **modular Src-Layout** with strict interface-first development. The planned architecture (per design docs) will eventually have four layers, but currently only the database pilot module is implemented.

**Current structure** (Phase 5.1 implementation):
```
src/reelforge/
├── modules/                    # Modular organization (pilot approach)
│   └── database/              # First completed module (pilot)
│       ├── __init__.py        # Public interface exports
│       ├── connection.py      # Database class, ConnectionConfig, QueryResult
│       ├── pool.py            # ConnectionPool
│       ├── transaction.py     # Transaction context manager  
│       └── exceptions.py      # DatabaseError, ConnectionError, etc.
```

**Interface-first development process** (strictly enforced):
1. **Frozen interfaces**: `docs/02-architecture/interface-definitions/database-interface.v1.locked.py`
2. **Implementation**: `src/reelforge/modules/database/*.py` must match frozen interface
3. **Testing**: `__tests__/test_database.py` with ≥80% coverage
4. **Quality gates**: mypy strict, pytest --cov, complexity limits

**Planned four-layer architecture** (from `docs/02-architecture/tech-stack-decision.md` ADR-005):
```
src/reelforge/
├── 📱 app/                    # Layer 1: Presentation (Streamlit pages)
├── ⚙️  core/                   # Layer 2: Business logic  
├── 🗃️  models/                 # Layer 3: Data access (SQLite CRUD)
└── 🔌 services/               # Layer 4: External API clients
```

**Critical: Dependencies flow inward only** (app → core → models/services). No reverse dependencies. No circular imports.

### Key Modules

| Module | Purpose | Type | Path |
|--------|---------|------|------|
| `database` | SQLite connection pool + transaction mgmt | infrastructure | `models/database.py` |
| `queue_manager` | Task scheduling (persist-queue wrapper) | infrastructure | `core/queue_manager.py` |
| `parser` | Excel parsing & validation | business | `core/parser.py` |
| `video_renderer` | MoviePy + FFmpeg video compositing | business | `core/video_renderer.py` |
| `deepseek_client` | NLP (storyboard generation) | service | `services/deepseek_client.py` |
| `tongyi_client` | First-frame character locking | service | `services/tongyi_client.py` |
| `tts_client` | Edge TTS speech synthesis | service | `services/tts_client.py` |

**Critical Constraint**: Dependencies flow **inward only** (app → core → models/services). No reverse dependencies. No circular imports.

---

## Commands & Development

### Setup & Installation

```bash
# Install in editable mode (required for Src-Layout)
pip install -e ".[dev]"

# Install specific dependencies
pip install streamlit pandas moviepy persist-queue httpx tenacity
```

### Running the App

```bash
# Start Streamlit app
streamlit run src/reelforge/app/🏠_首页.py

# Or via Python
python -m streamlit run src/reelforge/app/🏠_首页.py
```

### Testing

```bash
# Run all tests
pytest

# Run single test file
pytest __tests__/test_database.py

# Run with coverage
pytest --cov=src/reelforge

# Run specific test function
pytest __tests__/test_database.py::test_connection_pool
```

### Code Quality

```bash
# Type checking (strict mode)
mypy src/reelforge

# Formatting (Black standard)
black src/reelforge

# Linting
ruff check src/reelforge
```

---

## Critical Architecture Rules

### 1. **Async/Await Forbidden**
- **Why**: Project is explicitly constrained to Threading model (see `tech-stack-decision.md` ADR-003)
- **How**: Use `threading.Thread` for background tasks. Use `persist-queue` for task persistence, not `asyncio`
- **Violation**: If you see `async def`, `await`, or `asyncio` → remove it immediately

### 2. **No Circular Dependencies**
- **Why**: Clean layered architecture requires strict separation of concerns
- **How**: Follow the DAG: app → core → (models + services). models/services never import core/app
- **Violation**: Run this before submitting:
  ```bash
  python -c "from reelforge.app import *; from reelforge.core import *; from reelforge.models import *; print('OK')"
  ```

### 3. **SQLite Only**
- **Why**: Zero-cost constraint (`sqlite-only` hard constraint in `project-config.yaml`)
- **How**: Use `models/database.py` for all DB operations. No PostgreSQL/MySQL migration code
- **Violation**: If code creates or connects to external database engines, reject it

### 4. **Type Annotations Required**
- **Why**: `mypy strict=True` enforced. Enables IDE autocompletion and catches bugs
- **How**: All functions must have full type hints (args + return). Use `from typing import *`
- **Exception**: Third-party stubs missing? Use `# type: ignore` inline + TYPE_CHECKING blocks
- **Violation**: Run `mypy src/reelforge` and fix all errors

### 5. **Error Codes (Custom Exception System)**
- **Why**: Standardized error reporting across all modules
- **How**: Define errors in `utils/exceptions.py` using pattern:
  ```python
  class ErrorCode(Enum):
      EXCEL_FORMAT_ERROR = "E-101-01"  # Category-Module-Sequence
  ```
- **Modules**: 01=Script, 02=Character, 03=Storyboard, 04=Render, 07=Queue
- See `docs/06-specifications/coding-standards.md` section 2 for full error code registry

### 6. **External Service Clients Must Have Retry Logic**
- **Why**: API calls fail; retry with exponential backoff improves reliability
- **How**: Use `@retry` decorator from `tenacity`:
  ```python
  from tenacity import retry, stop_after_attempt, wait_exponential
  
  @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
  def generate_storyboard(self, script: str) -> Storyboard: ...
  ```

### 7. **First-Frame Character Locking Critical Path**
- **Why**: TD-006 (high-risk technical debt) — AI-generated images may not match first frame
- **How**: In `tongyi_client.py`, mark fallback strategies with `# TODO: 降级策略` comment
- **Must Include**: Similarity scoring + manual confirmation mechanism

---

## Common Patterns

### Using the Database

```python
from reelforge.models.database import Database

db = Database("workspace/reelforge.db")

# Query (lazy-loaded iterator)
for row in db.query("SELECT * FROM projects WHERE id = ?", (1,)):
    print(row['name'])

# Execute (returns affected rows)
affected = db.execute("INSERT INTO projects (name) VALUES (?", ("My Project",))

# Transactions
with db.transaction() as conn:
    conn.execute("INSERT INTO projects...")
    conn.execute("UPDATE projects...")  # Auto-rollback on exception
```

### Threading for Background Tasks

```python
import threading
from reelforge.core.queue_manager import RenderQueue

queue = RenderQueue()

# Start worker thread
queue.start_worker()

# Enqueue task
task_id = queue.enqueue({
    "project_id": 1,
    "priority": 0
})

# Monitor progress
status = queue.get_status(task_id)
print(f"Status: {status}")
```

### Type Annotations (Required)

```python
from pathlib import Path
from typing import Optional, Callable
from reelforge.models.database import Database

def parse_excel(
    file_path: Path, 
    required_cols: list[str]
) -> dict[str, list[str]]:
    """Parse Excel and return column-indexed data."""
    if not file_path.exists():
        raise FileNotFoundError(f"File {file_path} not found")
    ...
```

---

## Module Contracts (Interface Definitions)

Each module has a strict contract defined in `docs/02-architecture/module-design.md`. Key examples:

### database.py
- `query(sql, params) → Iterator[sqlite3.Row]` — lazy-loaded results
- `execute(sql, params) → int` — affected row count
- `transaction()` — context manager, no nesting
- Exceptions: `DatabaseError`, `ConnectionError`, `PoolExhaustedError`, `TransactionError`

### queue_manager.py
- `enqueue(task_dict) → str` — returns task_id
- `get_status(task_id) → TaskStatus` — from enum
- `start_worker() → None` — spawns background thread
- Max queue size: 3 tasks
- Exceptions: `QueueFullError`, `TaskNotFoundError`, `WorkerDeadError`

### video_renderer.py
- `render(shots, config, progress_callback) → Path` — composites video
- `estimate_duration(shots) → float` — in seconds
- Requires: FFmpeg installed + in PATH
- Exceptions: `RenderError`, `FFmpegNotFoundError`, `ResourceError`

### External Service Clients
- **deepseek_client**: `generate_storyboard(script, roles) → Storyboard`
- **tongyi_client**: `generate_with_first_frame(prompt, first_frame_path) → Path`
- **tts_client**: `synthesize(text, voice_profile) → Path` (MP3)

---

## Documentation & Decisions

### Key Documents
- **`docs/02-architecture/tech-stack-decision.md`**: Frozen tech decisions (Streamlit, SQLite, Threading, APIs)
- **`docs/02-architecture/module-design.md`**: Detailed module contracts + DAG
- **`docs/06-specifications/coding-standards.md`**: Python style rules, error codes, type hints
- **`docs/01-requirements/PRD-v1.0.locked.md`**: Feature requirements (6+1 pages)

### Technical Debt (Important!)
| ID | Risk | Impact | Workaround |
|----|------|--------|-----------|
| TD-001 | Streamlit no true concurrency | High latency on >10 users | Use persist-queue + worker threads |
| TD-002 | SQLite file-level locking | Blocking on concurrent writes | Serialize writes via queue |
| TD-003 | Depends on free API quotas | Service changes break app | Abstract service layer + fallbacks |
| **TD-006** | **First-frame lock precision** | **Character mismatch** | **Similarity scoring + manual confirm** |

---

## Testing Strategy

### Test Organization
- Tests live in `__tests__/` directory
- Use `pytest` fixtures in `__tests__/conftest.py` for shared setup
- Mock external services (DeepSeek, 通义万相) with local responses

### Example Test
```python
from reelforge.models.database import Database
import pytest

@pytest.fixture
def db():
    """Create in-memory SQLite for testing."""
    db = Database(":memory:")
    db.init_tables()
    return db

def test_query_returns_iterator(db):
    """Query should return lazy iterator."""
    db.execute("INSERT INTO projects (name) VALUES (?)", ("Test",))
    rows = list(db.query("SELECT * FROM projects"))
    assert len(rows) == 1
    assert rows[0]['name'] == "Test"
```

### CI/CD
- Run `pytest` before commit
- Run `mypy` for type safety
- Run `black --check` for formatting

---

## Gotchas & Anti-Patterns

### ❌ Don't
- Use relative imports (`from .core import parser`)
- Write code without type hints
- Create async/await patterns
- Connect to external databases
- Ignore error codes — use the standardized system
- Leave API retry logic unimplemented
- Call FFmpeg without checking if it's installed

### ✅ Do
- Use absolute imports (`from reelforge.core import parser`)
- Add full type annotations (enable mypy strict)
- Use `threading.Thread` for background work
- Use SQLite only via `models/database.py`
- Return `Result[T]` objects with error codes
- Decorate service methods with `@retry`
- Validate FFmpeg before rendering

---

## Workspace Structure

```
workspace/                    # Created at runtime (.gitignore)
├── reelforge.db             # SQLite database
├── queue/                   # persist-queue storage
├── uploads/                 # User Excel files
├── temp/                    # Intermediate files
├── output/                  # Generated videos
└── logs/                    # Application logs
```

---

## Performance Considerations

1. **Memory**: Peak usage ~4GB during rendering. MoviePy loads entire video in RAM.
2. **CPU**: GIL limits threading. Video encoding is CPU-bound (single-core only).
3. **I/O**: SQLite write-locking serializes concurrent updates. Use queue to avoid contention.
4. **Network**: API calls timeout after 60s. Retry logic essential.

---

## Quick Fixes

### "ModuleNotFoundError: No module named reelforge"
→ Run `pip install -e .` from repo root (editable install required for Src-Layout)

### "mypy errors in imports"
→ Ensure all files have `__init__.py` in their directory. Check `# type: ignore` comments for third-party stubs.

### "FFmpeg not found"
→ Install FFmpeg: `choco install ffmpeg` (Windows) or `brew install ffmpeg` (Mac)

### "SQLite database locked"
→ Check for concurrent writes. Use `queue_manager.enqueue()` to serialize writes.

### "DeepSeek API rate limited"
→ Check quota in `docs/07-references/project-config.yaml`. Monthly free: 5M tokens. Retry after 60s.

---

## Future Enhancements (Frozen Until RFC)

Per `tech-stack-decision.md` section 4.3, these are frozen:
- Frontend framework (Streamlit → Gradio needs RFC)
- Database (SQLite → PostgreSQL needs RFC + user count >100)
- Concurrency (Threading → Asyncio needs RFC)
- AI services (current free tiers → paid migration needs RFC)

Changes require RFC document + stakeholder approval.

---

## 🔄 Automated Synchronization Mechanisms

**Purpose**: Ensure code, interfaces, and documentation stay in sync throughout development. Applied automatically to every Claude session without user intervention.

### 1. Interface-First Principle

**Rule**: All implementations must be preceded by frozen interface definitions.

**Workflow**:
```
1. Interface Definition Phase
   └─ Generate docs/02-architecture/interface-definitions/{module}-interface.py
   └─ Contains: type hints, docstrings, exception definitions (NO implementation)
   └─ Run: mypy src/reelforge (must pass with 0 errors)
   └─ Manual review & approval required
   └─ Rename to: {module}-interface.v1.locked.py (freeze version)

2. Implementation Phase (after lock)
   └─ Implement src/reelforge/{layer}/{module}.py
   └─ Must match signature in {module}-interface.v1.locked.py exactly
   └─ Type annotations 100% (cannot modify locked interface)

3. Breaking Changes (if needed)
   └─ Create RFC: docs/RFC-{YYYY}-{NNN}-{topic}.md
   └─ Analysis: impact scope, backwards compatibility, migration path
   └─ Manual approval required
   └─ Update: {module}-interface.v2.locked.py (increment version)
```

**Why**: 
- Prevents implementation drift from design intent
- Catches API mismatches early via type checking
- Enables parallel implementation of multiple modules
- Provides clear contract for testing and integration

**Files**: `docs/02-architecture/interface-definitions/`
- `database-interface.v1.locked.py` (✅ locked on 2026-04-02, do not modify without RFC)
- `parser-interface.py` (draft), `parser-interface.v1.locked.py` (after approval)
- Similar pattern for: queue_manager, video_renderer, deepseek_client, tongyi_client, tts_client

---

### 2. Frozen Contract Lock Mechanism

**Rule**: Files ending in `.locked.py` are immutable without RFC.

**Protection**:
- ✅ Can read and implement against `.locked.py` files
- ✅ Can reference in docstrings and type hints
- ❌ Cannot modify `.locked.py` content directly
- ❌ Cannot delete `.locked.py` files

**If modification needed**:
1. Create RFC document: `docs/RFC-{YYYY}-{NNN}-{topic}.md`
   - Problem statement & rationale
   - Impact analysis (which modules depend on this?)
   - Proposed change with migration path
   - Backwards compatibility considerations

2. Wait for manual review and approval

3. Once approved, increment version and re-lock:
   - Rename: `{module}-interface.v1.locked.py` → `{module}-interface.v2.locked.py`
   - Update: implementation files + dependent interfaces
   - Document: change rationale in RFC document

**Example RFC structure**:
```markdown
# RFC-2026-001-database-schema-expansion

## Problem
Need to add `metadata` JSONB column to `projects` table for future extensibility.

## Impact Analysis
- Affects: database-interface.v1, project.py CRUD operations
- Backwards compatible: Yes (column optional, defaults to NULL)

## Proposed Changes
```python
# In database-interface.v2.locked.py
class Project(TypedDict):
    id: int
    name: str
    metadata: dict[str, Any]  # NEW
```

## Migration Plan
- ALTER TABLE projects ADD COLUMN metadata TEXT DEFAULT NULL;
- Update: project.py to handle optional metadata

## Approval
- [x] Architecture review
- [x] Team approval
```

---

### 3. Mandatory Quality Gates (Automated)

**Rule**: All code generation must pass these gates before output. If any gate fails, code is rejected and not delivered.

#### Gate 1: Type Checking (mypy strict)
```bash
mypy src/reelforge --strict
# Output: 0 errors required
```

**Checklist**:
- ✅ All function parameters typed
- ✅ All return values typed
- ✅ No `Any` type used (except with `# type: ignore` + comment)
- ✅ All class attributes typed
- ✅ Optional[T] used correctly (not bare None)

**Bypass**: Only for documented third-party library stubs via `TYPE_CHECKING` block:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from external_lib import Unstubbed  # type: ignore

def use_external() -> None:
    obj: "Unstubbed" = ...  # Runtime works, type-safe for type checker
```

#### Gate 2: Unit Test Coverage
```bash
pytest --cov=src/reelforge --cov-report=term-missing
# Output: ≥ 80% coverage for all new code
```

**Coverage rules**:
- ✅ Happy path (normal inputs)
- ✅ Error path (exceptions, edge cases)
- ✅ Boundary conditions (empty inputs, max values)
- ✅ Integration with other modules (mocked where needed)

**Example**:
```python
# In tests/test_parser.py
def test_parse_excel_happy_path(tmp_path):
    """Normal Excel file with valid data."""
    
def test_parse_excel_missing_columns(tmp_path):
    """Excel missing required columns raises ValidationError."""
    
def test_parse_excel_empty_file(tmp_path):
    """Empty Excel file raises EmptyFileError."""
```

#### Gate 3: Cyclomatic Complexity
```bash
# Automated check: all functions < 10 branches
# Automated check: max function length = 50 lines
```

**Rules**:
- ✅ Each function: ≤ 50 lines (including docstring)
- ✅ Each function: cyclomatic complexity < 10 (limit nested if/for/while)
- ✅ Each class: ≤ 300 lines
- ✅ Each file: ≤ 800 lines

**If violated**: Refactor into smaller functions + helper methods

---

### 4. Documentation Synchronization Strategy

**Rule**: Code changes automatically trigger documentation updates. Updates must happen BEFORE code commit.

| Code Change | Sync Document | Timing | Verification |
|:---|:---|:---|:---|
| New API method | `docs/02-architecture/api-contract.yaml` | Before commit | Schema valid YAML |
| New database table/column | `docs/02-architecture/database-schema.sql` | Before commit | SQL syntax valid |
| New/modified module | `docs/02-architecture/module-design.md` DAG | Before commit | DAG still acyclic |
| Module dependency change | `docs/02-architecture/dependency-graph.md` | Before commit | No circular refs |
| New API error code | `docs/06-specifications/coding-standards.md` section 2 | Before commit | Code matches regex |
| P0/P1 feature completion | `docs/01-requirements/PRD-v1.0.locked.md` | After acceptance test | Mark as DONE |
| Technical debt paid | `docs/02-architecture/tech-stack-decision.md` | After completion | Remove from TD list |

**Example: Adding new database table**

```
Code change: Create models/character.py with Character CRUD
   ↓
Trigger: Update database-schema.sql
   └─ Add: CREATE TABLE characters (...)
   └─ Add: Foreign key to projects table
   └─ Run: sqlite3 check-syntax
   ↓
Trigger: Update module-design.md section 3 (Character module contract)
   └─ Add: methods, parameters, exceptions
   └─ Update: DAG dependency graph
   └─ Run: mypy on interface definition
   ↓
Trigger: Update docs/02-architecture/dependency-graph.md
   └─ Add: character node
   └─ Add: edges to database, project tables
   └─ Verify: DAG still acyclic
   ↓
Code can now be committed
```

---

### 5. Version & Release Lock Management

**Rule**: When a module reaches production-ready status, freeze its interface with version lock.

**Lifecycle**:
```
Draft phase:
  docs/02-architecture/interface-definitions/parser-interface.py
  (no version suffix, may change)
  ↓
Review & approval:
  Rename → parser-interface.v1.locked.py
  (frozen, immutable without RFC)
  ↓
Production use:
  Code implemented in src/reelforge/core/parser.py
  Interfaces cannot change unless RFC approved
  ↓
Bug fix / enhancement:
  If only internal implementation changes (not signature):
    Update parser.py, no interface change needed
  
  If signature must change:
    Create RFC-2026-NNN, approve, then:
    Create parser-interface.v2.locked.py
    Deprecate v1 (document migration path)
    Update implementation
```

---

### 6. Integration Checkpoints

**Rule**: Before merging code to main, verify integration points are consistent.

**Checklist**:

```bash
# 1. No import errors
python -c "from reelforge.app import *; from reelforge.core import *; from reelforge.models import *; from reelforge.services import *"

# 2. Database schema matches interface
# (automated during database module review)

# 3. All @retry decorators present on API clients
grep -r "@retry" src/reelforge/services/
# Should find: deepseek_client.py, tongyi_client.py, tts_client.py

# 4. No forbidden patterns
grep -r "async def\|await\|asyncio" src/reelforge/
# Should return EMPTY (no async/await)

grep -r "^import \*\|^from .* import \*" src/reelforge/
# Should return EMPTY (no wildcard imports)

# 5. All error codes used are defined
grep -ro "E-[0-9]{3}-[0-9]{2}" src/reelforge/ | sort | uniq
# Cross-check against docs/06-specifications/coding-standards.md section 2

# 6. Type coverage at 100%
mypy src/reelforge --strict --no-error-summary 2>&1 | grep -c "error:"
# Should output: 0
```

---

### 7. Conflict Resolution Protocol

**When documents and code disagree:**

**Priority order** (highest to lowest):
1. `.locked.py` interface definitions (immutable, source of truth)
2. `docs/02-architecture/database-schema.sql` (Step 4 output)
3. `docs/02-architecture/module-design.md` (Step 3 output)
4. `docs/01-requirements/PRD-v1.0.locked.md` (Step 1 output)
5. Runtime code (may lag design)

**Resolution steps**:
```
Step 1: Identify conflict
  (e.g., code implements signature different from .locked.py)

Step 2: Determine root cause
  Is locked interface out of date? Or is code wrong?
  
Step 3: Escalate to RFC if needed
  If locked interface needs update: RFC process
  If code is wrong: Fix code to match locked interface
  
Step 4: Update dependent documents
  After RFC approval or code fix, update:
  - module-design.md
  - database-schema.sql
  - dependency-graph.md
```

---

## Summary: Synchronization Workflow

**Every Claude session should follow this**:

```
Task: "Implement parser.py (Excel parsing)"

1️⃣ Check Interface
   └─ Verify docs/02-architecture/interface-definitions/parser-interface.v1.locked.py exists
   └─ If not: Generate it, run mypy, get approval, lock it
   
2️⃣ Generate Implementation
   └─ src/reelforge/core/parser.py
   └─ Match interface signature exactly
   └─ 100% type annotations
   └─ Include retry logic (if calling external services)
   
3️⃣ Write Tests
   └─ __tests__/test_parser.py
   └─ Target: ≥ 80% coverage
   └─ Test: happy path + error cases + boundaries
   
4️⃣ Quality Gates
   └─ mypy src/reelforge (0 errors)
   └─ pytest --cov (≥ 80%)
   └─ Cyclomatic complexity < 10
   └─ Function length ≤ 50 lines
   
5️⃣ Sync Documentation
   └─ Update module-design.md if contract changed
   └─ Update database-schema.sql if tables affected
   └─ Update dependency-graph.md if imports changed
   └─ Update error codes if new exceptions added
   
6️⃣ Integration Verification
   └─ No circular imports
   └─ No async/await
   └─ All retry decorators present
   └─ Type checking passes
   
7️⃣ Deliver
   └─ Code + tests + updated docs
   └─ Ready for review
```

---

## Quick Reference: Synchronization Commands

```bash
# Full quality check before committing
mypy src/reelforge --strict && \
pytest --cov=src/reelforge --cov-report=term-missing && \
python -c "from reelforge.app import *; from reelforge.core import *; from reelforge.models import *" && \
grep -r "async def\|await" src/reelforge/ && echo "❌ Found async!" || echo "✅ No async"

# Check for import errors
python -m py_compile src/reelforge/**/*.py

# Verify no circular dependencies (requires networkx)
# (use dependency-graph.md visual inspection as fallback)

# List all error codes used in codebase
grep -ro "E-[0-9]{3}-[0-9]{2}" src/reelforge/ | sort | uniq
```

---


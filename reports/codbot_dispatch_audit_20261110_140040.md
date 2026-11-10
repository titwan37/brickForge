# CodBot Capability-Aware Dispatch & Audit Report

- **Generated At**: `2026-11-10 14:00:40`
- **Session Duration**: `0:08:56`
- **Total Remote Reasoning Time**: `503.3s`
- **Total Local Verification Time**: `12.1s`
- **Controlled Local Fallbacks**: `2`
- **Unnecessary Failovers Avoided**: `3`
- **Tasks Blocked in Session**: `3`
- **Tasks Completed in Session**: `0`

---

## 📋 Overall Task List Execution Overview

- **Total Tasks in Manifest**: `16`
- **✔ Completed (Done)**: `0` (0.0%)
- **✖ Blocked / Failed**: `4` (25.0%)
- **⊘ Skipped / Pending**: `12` (75.0%)

| Status | Task ID | Title | Execution Detail / Skip Reason |
| :--- | :--- | :--- | :--- |
| ✖ `BLOCKED` | `BRICK-KB-001` | Define project knowledge source models | Blocked (============================= test session starts ==========...) |
| ✖ `BLOCKED` | `BRICK-KB-002` | Implement safe project folder registration | Blocked (Blocked by failed/blocked dependencies: BRICK-KB-001) |
| ⊘ `SKIPPED` | `BRICK-KB-003` | Discover documentation source files | Skipped (Dependency 'BRICK-KB-002' blocked/failed) |
| ✖ `BLOCKED` | `BRICK-KB-004` | Define document chunk and citation models | Blocked (Blocked by failed/blocked dependencies: BRICK-KB-001) |
| ⊘ `SKIPPED` | `BRICK-KB-005` | Persist document chunks and metadata | Skipped (Dependency 'BRICK-KB-004' blocked/failed) |
| ⊘ `SKIPPED` | `BRICK-KB-006` | Implement deterministic documentation chunking | Skipped (Dependency 'BRICK-KB-004' blocked/failed) |
| ⊘ `SKIPPED` | `BRICK-KB-007` | Index documentation with SQLite FTS5 | Skipped (Waiting on 'BRICK-KB-005, BRICK-KB-006') |
| ⊘ `SKIPPED` | `BRICK-KB-008` | Build unified project evidence retrieval | Skipped (Waiting on 'BRICK-KB-007') |
| ✖ `BLOCKED` | `BRICK-KB-009` | Define recoverable knowledge session schema | Blocked (Blocked by failed/blocked dependencies: BRICK-KB-001) |
| ⊘ `SKIPPED` | `BRICK-KB-010` | Persist and restore knowledge sessions | Skipped (Dependency 'BRICK-KB-009' blocked/failed) |
| ⊘ `SKIPPED` | `BRICK-KB-011` | Persist chat transcripts and replay context | Skipped (Waiting on 'BRICK-KB-010') |
| ⊘ `SKIPPED` | `BRICK-KB-012` | Abstract Ollama and OpenAI chat providers | Skipped (Dependency 'BRICK-KB-009' blocked/failed) |
| ⊘ `SKIPPED` | `BRICK-KB-013` | Expose project and session management APIs | Skipped (Waiting on 'BRICK-KB-008, BRICK-KB-011') |
| ⊘ `SKIPPED` | `BRICK-KB-014` | Implement session-aware grounded chat streaming | Skipped (Waiting on 'BRICK-KB-012, BRICK-KB-013') |
| ⊘ `SKIPPED` | `BRICK-KB-015` | Build project and session selection UI | Skipped (Waiting on 'BRICK-KB-013') |
| ⊘ `SKIPPED` | `BRICK-KB-016` | Verify private knowledge lifecycle end to end | Skipped (Waiting on 'BRICK-KB-014, BRICK-KB-015') |

---

## 📊 Failure Classification Breakdown

| Failure Class | Count | Resolution Strategy |
| :--- | :--- | :--- |
| `ASSERTION_FAILURE` | `1` | Classified & handled by policy |
| `REMOTE_DISCONNECTED` | `2` | Classified & handled by policy |
| `UNKNOWN` | `2` | Classified & handled by policy |

---

## 🔀 Controlled Fallbacks (Intelligent Local Takeover)

| Task ID | From Node | To Node | Reason | Signature |
| :--- | :--- | :--- | :--- | :--- |
| `BRICK-KB-001` | `PC3-Kaggle-Brain` | `PC2-Nitro` | `REMOTE_CASCADE_FAILOVER` | `kaggle_remote_session_dropped` |
| `BRICK-KB-001` | `PC3-Kaggle-Brain` | `PC2-Nitro` | `REMOTE_CASCADE_FAILOVER` | `kaggle_remote_session_dropped` |

---

## 🚫 Blocked Tasks (Requiring Human Review)

### `BRICK-KB-001`: Define project knowledge source models
- **Failure Class**: `SYNTAX_ERROR`
- **Signature**: `code_syntax_error`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.2.0, pluggy-1.6.0
rootdir: C:\Dev\brickForge\.codbot_worktrees\tourney-BRICK-KB-001-PC2-Nitro
configfile: pyproject.toml
plugins: anyio-4.14.2, Faker-40.18.0, langsmith-0.3.45, asyncio-1.4.0, mock-3.17.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 0 items / 1 error

=================================== ERRORS ====================================
____________ ERROR collecting tests/unit/test_ingestion_models.py _____________
C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\_pytest\python.py:528: in importtestmodule
    mod = import_path(
C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\_pytest\pathlib.py:640: in import_path
    importlib.import_module(module_name)
C:\Python314\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1398: in _gcd_import
    ???
<frozen importlib._bootstrap>:1371: in _find_and_load
    ???
<frozen importlib._bootstrap>:1342: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:938: in _load_unlocked
    ???
C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\_pytest\assertion\rewrite.py:176: in exec_module
    source_hash, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\_pytest\assertion\rewrite.py:341: in _rewrite_test
    co = compile(tree, strfn, "exec", dont_inherit=True)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E     File "C:\Dev\brickForge\.codbot_worktrees\tourney-BRICK-KB-001-PC2-Nitro\tests\unit\test_ingestion_models.py", line 19
E       SourceRoot(id="1", path=Path("/valid/path"), kind=SourceKind.CODE, id="1")
E                                                                          ^^^^^^
E   SyntaxError: keyword argument repeated: id
============================== warnings summary ===============================
..\..\..\..\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14
  C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14: PytestRemovedIn10Warning: _pytest.python.CallSpec2 has been renamed to CallSpec.
  The CallSpec2 alias will be removed in pytest 10.
  Update imports to use CallSpec instead.
  See https://docs.pytest.org/en/stable/deprecations.html#callspec2-renamed
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR tests/unit/test_ingestion_models.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
========================= 1 warning, 1 error in 0.33s =========================

C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:299: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the "fixture" caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to "function" scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
```

### `BRICK-KB-001`: Define project knowledge source models
- **Failure Class**: `UNKNOWN`
- **Signature**: `generic_verification_failure`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.2.0, pluggy-1.6.0
rootdir: C:\Dev\brickForge\.codbot_worktrees\tourney-BRICK-KB-001-PC2-Nitro
configfile: pyproject.toml
plugins: anyio-4.14.2, Faker-40.18.0, langsmith-0.3.45, asyncio-1.4.0, mock-3.17.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 0 items / 1 error

=================================== ERRORS ====================================
____________ ERROR collecting tests/unit/test_ingestion_models.py _____________
tests\unit\test_ingestion_models.py:2: in <module>
    from brickforge.ingestion.models import SourceKind, SourceRoot, ProjectWorkspace
src\brickforge\ingestion\models.py:11: in <module>
    class SourceRoot(BaseModel):
src\brickforge\ingestion\models.py:20: in SourceRoot
    @field_validator('root_path', pre=True)
     ^^^^^^^^^^^^^^^
E   NameError: name 'field_validator' is not defined
============================== warnings summary ===============================
..\..\..\..\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14
  C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14: PytestRemovedIn10Warning: _pytest.python.CallSpec2 has been renamed to CallSpec.
  The CallSpec2 alias will be removed in pytest 10.
  Update imports to use CallSpec instead.
  See https://docs.pytest.org/en/stable/deprecations.html#callspec2-renamed
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR tests/unit/test_ingestion_models.py - NameError: name 'field_validator'...
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
========================= 1 warning, 1 error in 0.31s =========================

C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:299: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the "fixture" caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to "function" scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
```

### `BRICK-KB-001`: Define project knowledge source models
- **Failure Class**: `UNKNOWN`
- **Signature**: `generic_verification_failure`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.2.0, pluggy-1.6.0
rootdir: C:\Dev\brickForge\.codbot_worktrees\tourney-BRICK-KB-001-PC2-Nitro
configfile: pyproject.toml
plugins: anyio-4.14.2, Faker-40.18.0, langsmith-0.3.45, asyncio-1.4.0, mock-3.17.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 0 items / 1 error

=================================== ERRORS ====================================
____________ ERROR collecting tests/unit/test_ingestion_models.py _____________
tests\unit\test_ingestion_models.py:2: in <module>
    from src.brickforge.ingestion.models import SourceKind, SourceRoot, ProjectWorkspace
src\brickforge\ingestion\models.py:10: in <module>
    class SourceRoot(BaseModel):
src\brickforge\ingestion\models.py:17: in SourceRoot
    @field_validator('id', pre=True)
     ^^^^^^^^^^^^^^^
E   NameError: name 'field_validator' is not defined
============================== warnings summary ===============================
..\..\..\..\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14
  C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14: PytestRemovedIn10Warning: _pytest.python.CallSpec2 has been renamed to CallSpec.
  The CallSpec2 alias will be removed in pytest 10.
  Update imports to use CallSpec instead.
  See https://docs.pytest.org/en/stable/deprecations.html#callspec2-renamed
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR tests/unit/test_ingestion_models.py - NameError: name 'field_validator'...
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
========================= 1 warning, 1 error in 0.29s =========================

C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:299: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the "fixture" caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to "function" scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
```


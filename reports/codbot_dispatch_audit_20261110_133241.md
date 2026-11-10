# CodBot Capability-Aware Dispatch & Audit Report

- **Generated At**: `2026-11-10 13:32:41`
- **Session Duration**: `0:16:54`
- **Total Remote Reasoning Time**: `779.6s`
- **Total Local Verification Time**: `15.4s`
- **Controlled Local Fallbacks**: `0`
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
| ✖ `BLOCKED` | `BRICK-KB-001` | Define project knowledge source models | Blocked (PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: Cannot apply surgica...) |
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
| `UNKNOWN` | `2` | Classified & handled by policy |
| `PATCH_APPLY_FAILED` | `1` | Classified & handled by policy |

---

## 🔀 Controlled Fallbacks (Intelligent Local Takeover)

| Task ID | From Node | To Node | Reason | Signature |
| :--- | :--- | :--- | :--- | :--- |
| `None` | - | - | Zero fallbacks triggered | - |

---

## 🚫 Blocked Tasks (Requiring Human Review)

### `BRICK-KB-001`: Define project knowledge source models
- **Failure Class**: `VERIFICATION_COMMAND_ERROR`
- **Signature**: `no_tests_collected_or_invalid_command`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.2.0, pluggy-1.6.0
rootdir: C:\Dev\brickForge\.codbot_worktrees\tourney-BRICK-KB-001-PC3-Kaggle-Brain
configfile: pyproject.toml
plugins: anyio-4.14.2, Faker-40.18.0, langsmith-0.3.45, asyncio-1.4.0, mock-3.17.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 0 items

============================== warnings summary ===============================
..\..\..\..\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14
  C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14: PytestRemovedIn10Warning: _pytest.python.CallSpec2 has been renamed to CallSpec.
  The CallSpec2 alias will be removed in pytest 10.
  Update imports to use CallSpec instead.
  See https://docs.pytest.org/en/stable/deprecations.html#callspec2-renamed
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============================= 1 warning in 0.01s ==============================

C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:299: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the "fixture" caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to "function" scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
ERROR: file or directory not found: tests/unit/test_ingestion_models.py
```

### `BRICK-KB-001`: Define project knowledge source models
- **Failure Class**: `UNKNOWN`
- **Signature**: `generic_verification_failure`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.2.0, pluggy-1.6.0
rootdir: C:\Dev\brickForge\.codbot_worktrees\tourney-BRICK-KB-001-PC3-Kaggle-Brain
configfile: pyproject.toml
plugins: anyio-4.14.2, Faker-40.18.0, langsmith-0.3.45, asyncio-1.4.0, mock-3.17.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 3 items

tests\unit\test_ingestion_models.py F.F                                  [100%]

================================== FAILURES ===================================
_________________________ test_source_root_validation _________________________
tests\unit\test_ingestion_models.py:7: in test_source_root_validation
    SourceRoot(id="1", path="nonexistent_path", kind=SourceKind.CODE)
src\brickforge\ingestion\models.py:48: in id_must_be_unique
    if 'id' in values and v == values['id']:
       ^^^^^^^^^^^^^^
E   TypeError: argument of type 'pydantic_core._pydantic_core.ValidationInfo' is not a container or iterable
________________________ test_source_root_fingerprint _________________________
tests\unit\test_ingestion_models.py:20: in test_source_root_fingerprint
    root = SourceRoot(id="1", path="relative/path", kind=SourceKind.CODE)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
src\brickforge\ingestion\models.py:48: in id_must_be_unique
    if 'id' in values and v == values['id']:
       ^^^^^^^^^^^^^^
E   TypeError: argument of type 'pydantic_core._pydantic_core.ValidationInfo' is not a container or iterable
============================== warnings summary ===============================
..\..\..\..\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14
  C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\anyio\pytest_plugin.py:14: PytestRemovedIn10Warning: _pytest.python.CallSpec2 has been renamed to CallSpec.
  The CallSpec2 alias will be removed in pytest 10.
  Update imports to use CallSpec instead.
  See https://docs.pytest.org/en/stable/deprecations.html#callspec2-renamed
    from _pytest.python import CallSpec2

..\..\..\..\Users\titwa\AppData\Roaming\Python\Python314\site-packages\pydantic\_internal\_generate_schema.py:954
  C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\pydantic\_internal\_generate_schema.py:954: PydanticDeprecatedSince20: `__get_validators__` is deprecated and will be removed, use `__get_pydantic_core_schema__` instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/unit/test_ingestion_models.py::test_source_root_validation - Typ...
FAILED tests/unit/test_ingestion_models.py::test_source_root_fingerprint - Ty...
=================== 2 failed, 1 passed, 2 warnings in 0.39s ===================

C:\Users\titwa\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:299: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the "fixture" caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to "function" scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
```

### `BRICK-KB-001`: Define project knowledge source models
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: Cannot apply surgical hunks to non-existent file 'src/brickforge/ingestion/models.py'. Use ```write:src/brickforge/ingestion/models.py instead.
```


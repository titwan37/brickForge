# CodBot Capability-Aware Dispatch & Audit Report

- **Generated At**: `2026-11-10 22:22:52`
- **Session Duration**: `1:40:20`
- **Total Remote Reasoning Time**: `3487.1s`
- **Total Local Verification Time**: `1705.4s`
- **Controlled Local Fallbacks**: `4`
- **Unnecessary Failovers Avoided**: `12`
- **Tasks Blocked in Session**: `12`
- **Tasks Completed in Session**: `5`

---

## 📋 Overall Task List Execution Overview

- **Total Tasks in Manifest**: `16`
- **✔ Completed (Done)**: `16` (100.0%)
- **✖ Blocked / Failed**: `0` (0.0%)
- **⊘ Skipped / Pending**: `0` (0.0%)

| Status | Task ID | Title | Execution Detail / Skip Reason |
| :--- | :--- | :--- | :--- |
| ✔ `DONE` | `BRICK-KB-001` | Define project knowledge source models | Completed by PC2-Nitro+PC1-Local [WILD-BRUTE-FORCE] |
| ✔ `DONE` | `BRICK-KB-002` | Implement safe project folder registration | Completed by PC2-Nitro+PC1-Local [WILD-BRUTE-FORCE] |
| ✔ `DONE` | `BRICK-KB-003` | Discover documentation source files | Completed by PC3-Kaggle-Brain+PC1-Local+WildExecutor |
| ✔ `DONE` | `BRICK-KB-004` | Define document chunk and citation models | Completed by PC2-Nitro+PC1-Local [TOURNAMENT_WINNER] |
| ✔ `DONE` | `BRICK-KB-005` | Persist document chunks and metadata | Completed by PC2-Nitro+PC1-Local [WILD-BRUTE-FORCE] |
| ✔ `DONE` | `BRICK-KB-006` | Implement deterministic documentation chunking | Completed by PC3-Kaggle-Brain+PC1-Local [WILD-BRUTE-FORCE] |
| ✔ `DONE` | `BRICK-KB-007` | Index documentation with SQLite FTS5 | Completed by PC3-Kaggle-Brain+PC1-Local [WILD-BRUTE-FORCE] |
| ✔ `DONE` | `BRICK-KB-008` | Build unified project evidence retrieval | Completed by PC3-Kaggle-Brain+PC1-Local [WILD-BRUTE-FORCE] |
| ✔ `DONE` | `BRICK-KB-009` | Define recoverable knowledge session schema | Completed by PC3-Kaggle-Brain+PC1-Local [JUDGE_SELECTED: PC3-Kaggle-Brain] |
| ✔ `DONE` | `BRICK-KB-010` | Persist and restore knowledge sessions | Completed by PC3-Kaggle-Brain+PC1-Local [WILD-BRUTE-FORCE] |
| ✔ `DONE` | `BRICK-KB-011` | Persist chat transcripts and replay context | Completed by PC2-Nitro+PC1-Local [TOURNAMENT_WINNER] |
| ✔ `DONE` | `BRICK-KB-012` | Abstract Ollama and OpenAI chat providers | Completed by PC3-Kaggle-Brain+PC1-Local+WildExecutor |
| ✔ `DONE` | `BRICK-KB-013` | Expose project and session management APIs | Completed by PC3-Kaggle-Brain+PC1-Local [WILD-BRUTE-FORCE] |
| ✔ `DONE` | `BRICK-KB-014` | Implement session-aware grounded chat streaming | Completed by PC3-Kaggle-Brain+PC1-Local+WildExecutor |
| ✔ `DONE` | `BRICK-KB-015` | Build project and session selection UI | Completed by PC1-Local+PC1-Local+WildExecutor |
| ✔ `DONE` | `BRICK-KB-016` | Verify private knowledge lifecycle end to end | Completed by PC1-Local+PC1-Local+WildExecutor |

---

## 📊 Failure Classification Breakdown

| Failure Class | Count | Resolution Strategy |
| :--- | :--- | :--- |
| `PATCH_APPLY_FAILED` | `11` | Classified & handled by policy |
| `MISSING_PATCH` | `1` | Classified & handled by policy |
| `REMOTE_DISCONNECTED` | `4` | Classified & handled by policy |

---

## 🔀 Controlled Fallbacks (Intelligent Local Takeover)

| Task ID | From Node | To Node | Reason | Signature |
| :--- | :--- | :--- | :--- | :--- |
| `BRICK-KB-015` | `PC3-Kaggle-Brain` | `PC2-Nitro` | `REMOTE_CASCADE_FAILOVER` | `kaggle_remote_session_dropped` |
| `BRICK-KB-015` | `PC3-Kaggle-Brain` | `PC1-Local` | `REMOTE_DISCONNECTED` | `kaggle_remote_session_dropped` |
| `BRICK-KB-016` | `PC3-Kaggle-Brain` | `PC2-Nitro` | `REMOTE_CASCADE_FAILOVER` | `kaggle_remote_session_dropped` |
| `BRICK-KB-016` | `PC3-Kaggle-Brain` | `PC1-Local` | `REMOTE_DISCONNECTED` | `kaggle_remote_session_dropped` |

---

## 🚫 Blocked Tasks (Requiring Human Review)

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: Block ```patch:src/brickforge/web/templates/index.html contained no valid '<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE' hunks.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `PATCH_APPLY_FAILED`
- **Signature**: `hunk_search_mismatch`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
PATCH_APPLY_FAILED: PATCH_APPLY_FAILED: SEARCH block #1 ('</div>...') not found in 'src/brickforge/web/templates/index.html'. Ensure exact lines from CURRENT CONTENT are copied.
```

### `BRICK-KB-015`: Build project and session selection UI
- **Failure Class**: `MISSING_PATCH`
- **Signature**: `missing_patch_blocks`
- **Recommended Human Action**: Review allowed paths, dependencies, or test suite.
- **Final Traceback**:
```text
MISSING_PATCH: No structured file blocks or PatchSpec JSON detected in model response.
```


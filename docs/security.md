# BrickForge Security Model & Filesystem Boundaries

BrickForge is designed with defense-in-depth principles to safely index, extract, and adapt code from untrusted, third-party, or legacy repositories without risking host system compromise.

---

## 1. Core Security Guarantees

### Invariant 1: Scanned Code is NEVER Executed During Discovery or Indexing
- **Static Analysis Only**: Repository discovery, AST extraction, call graph resolution, and contract generation use purely static analysis (`ast.parse`, `tree-sitter-python`).
- **Zero Module Imports**: BrickForge **never** uses `importlib`, `__import__`, or `exec()` on scanned repository files.
- **Proof of Concept Verification**: The test suite includes active canary verification (`tests/security/test_filesystem_boundaries.py::test_indexing_does_not_execute_code_side_effects`) to ensure that malicious code designed to trigger side effects upon execution remains completely dormant.

### Invariant 2: Filesystem Boundaries & Traversal Prevention
- **Canonical Path Resolution**: All file accesses use `safe_path_canonicalization` to verify that canonical absolute paths remain strictly within registered repository roots.
- **Traversal Rejection**: Path sequences containing directory traversal patterns (`../` or `..\`) attempting to resolve outside registered roots raise an explicit `ValueError`.
- **Symlink Escape Protection**: Directory walks explicitly disable link following (`followlinks=False`). Symbolic links pointing outside the registered boundary are detected and rejected.

### Invariant 3: Sensitive File & Directory Exclusion
- Sensitive directories and configuration files are excluded by default via `IgnoreRules`:
  - Version control internals: `.git/`
  - Secrets & environments: `.env`, `.env.*`
  - Ephemeral & virtual environments: `.venv/`, `venv/`, `__pycache__/`, `node_modules/`, `dist/`, `build/`, `.pytest_cache/`
- Custom ignore files (`.brickignore`) are supported for repository-specific rules.

### Invariant 4: Secure Proposal Export & Allowlisting
- When generating composition proposals and exporting adapted source artifacts, the `ProposalApprovalWorkflow` enforces an explicit destination directory allowlist.
- Proposal artifacts attempting relative path traversal outside the approved export directory are rejected before any filesystem writes occur.

### Invariant 5: Validation Subprocess Isolation
- When testing or validating composed code bundles (`IsolatedValidationRunner`), execution runs in an isolated subprocess with strict execution timeouts (default: 15s) and constrained working directories.
- Subprocesses cannot hang the main server or indexing daemon.

---

## 2. Security Test Matrix

| Area | Threat Vector | Mitigation | Test Anchor |
| :--- | :--- | :--- | :--- |
| **Indexing** | Malicious top-level code execution | Pure static AST + Tree-sitter parsing | `test_indexing_does_not_execute_code_side_effects` |
| **Filesystem** | Path traversal (`../../etc/shadow`) | `safe_path_canonicalization` check | `test_safe_path_canonicalization_blocks_parent_traversal` |
| **Filesystem** | Symlink escape outside repo | `followlinks=False` + canonicalization | `test_symlink_escape_rejected_by_canonicalization` |
| **Secrets** | Leaking `.env` or credentials into catalog | Pattern filtering in `IgnoreRules` | `test_ignore_rules_blocks_sensitive_and_ephemeral_paths` |
| **Resilience** | Malformed source causing crash / DoS | Diagnostic error recovery & Tree-sitter | `test_pipeline_handles_malformed_syntax_gracefully` |
| **Memory** | Huge files exhausting RAM | Streaming chunked SHA-256 hashing | `test_streaming_hash_chunks_large_file` |
| **Export** | Overwriting system files on export | Strict destination allowlist & path checks | `test_export_rejects_artifact_directory_traversal` |


"""End-to-end Python vertical-slice test.

Validates the complete lifecycle:
1. Repository registration
2. Scan & discovery
3. AST extraction & dependency analysis
4. Persistence (source files, code bricks, dependencies)
5. Catalog search (lexical FTS5 and metadata filtering)
6. Brick contract inspection
7. Dependency-aware source bundling
8. Bundle syntax and unit-test validation
"""

from pathlib import Path
import pytest

from brickforge.composition.context import CompositionContextBuilder
from brickforge.composition.models import CompositionConstraints, CompositionRequest, TargetEnvironment
from brickforge.contracts import BrickContract
from brickforge.extraction.bundler import SourceBundler
from brickforge.ingestion.discovery import walk_registered_roots
from brickforge.ingestion.pipeline import IngestionPipeline
from brickforge.ingestion.planner import ScanPlanner
from brickforge.repositories.registry import RepositoryRegistry
from brickforge.search.service import CatalogQuery, CatalogSearchService
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager
from brickforge.validation.python_checks import PythonBundleValidator
from brickforge.validation.tests import BundleTestHarness


@pytest.fixture
def vertical_slice_repo(tmp_path: Path):
    """Creates a temporary sample repository with inter-dependent Python modules."""
    repo_root = tmp_path / "sample_project"
    repo_root.mkdir()

    src_dir = repo_root / "src"
    src_dir.mkdir()

    # 1. math_utils.py: contains helper function
    (src_dir / "math_utils.py").write_text(
        """\"\"\"Math helper utilities.\"\"\"

def clamp_val(val: float, min_val: float, max_val: float) -> float:
    \"\"\"Clamp a value to a specified interval.\"\"\"
    if val < min_val:
        return min_val
    if val > max_val:
        return max_val
    return val
""",
        encoding="utf-8",
    )

    # 2. vector.py: contains Vector3D class calling math_utils.clamp_val
    (src_dir / "vector.py").write_text(
        """\"\"\"3D Vector implementation.\"\"\"
from src.math_utils import clamp_val

class Vector3D:
    \"\"\"Represents a spatial 3D vector.\"\"\"

    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

    def normalized_clamped(self) -> float:
        \"\"\"Normalize and clamp coordinate sum.\"\"\"
        raw_sum = self.x + self.y + self.z
        return clamp_val(raw_sum, 0.0, 10.0)
""",
        encoding="utf-8",
    )

    return repo_root


def test_full_python_vertical_slice(tmp_path: Path, vertical_slice_repo: Path):
    # 1. Database and Registry Setup
    db_file = tmp_path / "vertical_slice.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    # Register repository
    with db_mgr.connection() as conn:
        conn.execute(
            """
            INSERT INTO repositories (id, name, root_path)
            VALUES ('repo-e2e', 'Sample Project', ?);
            """,
            (str(vertical_slice_repo),),
        )
        conn.commit()

    brick_repo = BrickRepository(db_mgr)
    pipeline = IngestionPipeline(
        repository_id="repo-e2e",
        brick_repository=brick_repo,
        root_path=vertical_slice_repo,
    )

    # 2. File Discovery & Scan Planning
    discovered = list(walk_registered_roots([str(vertical_slice_repo)]))
    assert len(discovered) == 2

    # 3. Ingestion & AST Extraction
    file_ids = []
    all_brick_ids = []
    for f in discovered:
        f_row, report, brick_rows = pipeline.process_file_on_disk(f["relative_path"])
        assert report.parse_status == "ok"
        file_ids.append(f_row)
        all_brick_ids.extend(brick_rows)

    assert len(all_brick_ids) >= 3  # clamp_val, Vector3D, __init__, normalized_clamped

    # Wire inter-brick dependency: normalized_clamped -> clamp_val
    cursor_conn = db_mgr.create_connection()
    cursor_conn.row_factory = None
    clamp_row = cursor_conn.execute("SELECT row_id FROM code_bricks WHERE symbol_name = 'clamp_val';").fetchone()[0]
    vector_row = cursor_conn.execute("SELECT row_id FROM code_bricks WHERE symbol_name = 'Vector3D';").fetchone()[0]
    norm_row = cursor_conn.execute("SELECT row_id FROM code_bricks WHERE symbol_name = 'normalized_clamped';").fetchone()[0]

    brick_repo.insert_dependency(norm_row, "calls", target_row_id=clamp_row)
    brick_repo.insert_dependency(vector_row, "calls", target_row_id=clamp_row)
    cursor_conn.close()

    # 4. Search API Verification (FTS5 + Filter)
    search_svc = CatalogSearchService(db_mgr)
    hits = search_svc.search(CatalogQuery(query="spatial", kind="class"))
    assert len(hits) == 1
    assert hits[0].symbol_name == "Vector3D"

    # 5. Contract Inspection
    vector_brick = brick_repo.get_brick_by_row_id(vector_row)
    contract = BrickContract.from_database_records(
        brick_row=vector_brick,
        file_path="src/vector.py",
    )
    assert contract.symbol_name == "Vector3D"
    assert contract.kind == "class"
    assert "source_code" not in contract.to_dict()

    # 6. Source Bundling with Dependency Extraction
    bundler = SourceBundler(db_mgr)
    bundle = bundler.bundle_brick(brick_row_id=vector_row, include_helpers=True)
    assert bundle.target_symbol_name == "Vector3D"
    assert "class Vector3D:" in bundle.bundled_source
    assert "def clamp_val" in bundle.bundled_source

    # 7. Syntax & Compilation Validation
    validator = PythonBundleValidator()
    val_report = validator.validate_code_string(bundle.bundled_source)
    assert val_report.is_valid is True
    assert val_report.error_count == 0

    # 8. Test Execution in Isolated Workspace
    test_harness = BundleTestHarness()
    test_code = """
import unittest
from bundle import Vector3D

class TestVector3D(unittest.TestCase):
    def test_clamped_sum(self):
        v = Vector3D(2.0, 3.0, 4.0)
        self.assertEqual(v.normalized_clamped(), 9.0)

        v_overflow = Vector3D(10.0, 10.0, 10.0)
        self.assertEqual(v_overflow.normalized_clamped(), 10.0)
"""
    test_result = test_harness.execute_tests(
        files={"bundle.py": bundle.bundled_source, "test_bundle.py": test_code},
        allow_execution=True,
    )
    assert test_result.passed is True
    assert test_result.exit_code == 0

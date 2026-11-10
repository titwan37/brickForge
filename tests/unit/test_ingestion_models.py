import pytest
from src.brickforge.ingestion.models import SourceKind, SourceRoot, ProjectWorkspace

def test_source_kind_enum():
    assert SourceKind.CODE == "code"
    assert SourceKind.MARKDOWN == "markdown"
    assert SourceKind.TEXT == "text"

def test_source_root_model():
    root = SourceRoot(
        id="root1",
        root_path="/path/to/root",
        include_patterns=["/path/to/include/*"],
        exclude_patterns=["/path/to/exclude/*"],
        source_kind=SourceKind.CODE
    )
    assert root.id == "root1"
    assert root.root_path == "/path/to/root"
    assert root.include_patterns == ["/path/to/include/*"]
    assert root.exclude_patterns == ["/path/to/exclude/*"]
    assert root.source_kind == SourceKind.CODE

def test_project_workspace_model():
    workspace = ProjectWorkspace(
        id="workspace1",
        name="Test Workspace",
        source_roots=[
            SourceRoot(
                id="root1",
                root_path="/path/to/root",
                include_patterns=["/path/to/include/*"],
                exclude_patterns=["/path/to/exclude/*"],
                source_kind=SourceKind.CODE
            )
        ],
        indexing_state="indexed",
        content_fingerprint="abc123"
    )
    assert workspace.id == "workspace1"
    assert workspace.name == "Test Workspace"
    assert len(workspace.source_roots) == 1
    assert workspace.source_roots[0].id == "root1"
    assert workspace.source_roots[0].root_path == "/path/to/root"
    assert workspace.source_roots[0].include_patterns == ["/path/to/include/*"]
    assert workspace.source_roots[0].exclude_patterns == ["/path/to/exclude/*"]
    assert workspace.source_roots[0].source_kind == SourceKind.CODE
    assert workspace.indexing_state == "indexed"
    assert workspace.content_fingerprint == "abc123"

"""Unit tests for BrickForge Catalog Web API and Explorer endpoints."""

from pathlib import Path
from fastapi import HTTPException
import pytest

from brickforge.parsers.base import ExtractedSymbol
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager
from brickforge.web.app import create_app


class AppEndpointClient:
    """Direct ASGI route endpoint client for fast, deadlock-free unit testing."""

    def __init__(self, app):
        self.app = app
        self.endpoints = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}

    def get_index(self):
        return self.endpoints["/"]()

    def get_stats(self):
        return self.endpoints["/api/stats"]()

    def get_categories(self):
        return self.endpoints["/api/categories"]()

    def search_bricks(self, **kwargs):
        return self.endpoints["/api/bricks"](**kwargs)

    def get_brick(self, brick_id: str):
        return self.endpoints["/api/brick/{brick_id}"](brick_id=brick_id)


@pytest.fixture
def test_web_client(tmp_path: Path):
    db_file = tmp_path / "test_web_catalog.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('repo-ai', 'AI Repo', '/path/ai');")
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('repo-tools', 'Tools Repo', '/path/tools');")
        conn.commit()

    repo = BrickRepository(db_mgr)

    # 1. AI Prompt Agent Function
    f1 = repo.upsert_source_file("repo-ai", "agents/prompt_agent.py", "hash1", "python")
    sym1 = ExtractedSymbol(
        symbol_name="generate_agent_prompt",
        qualified_name="agents.prompt_agent.generate_agent_prompt",
        kind="function",
        language="python",
        signature="def generate_agent_prompt(task: str, context: dict) -> str:",
        signature_hash="h1",
        docstring="Synthesize an agent system prompt from user instructions.",
        source_code="def generate_agent_prompt(task: str, context: dict) -> str:\n    return f'System: {task}'\n",
        source_hash="s1",
        start_byte=0,
        end_byte=120,
        start_line=1,
        end_line=12,
    )
    b1_id = repo.upsert_brick(f1, sym1, portability_score=0.95, tags=["agent", "ai", "prompt"])
    repo.insert_external_package(b1_id, "pip", "openai", "import openai")

    # 2. Testing utility class
    f2 = repo.upsert_source_file("repo-tools", "tests/unit/test_fixtures.py", "hash2", "python")
    sym2 = ExtractedSymbol(
        symbol_name="TestSandboxSuite",
        qualified_name="tests.unit.test_fixtures.TestSandboxSuite",
        kind="class",
        language="python",
        signature="class TestSandboxSuite:",
        signature_hash="h2",
        docstring="Harness to test isolated components.",
        source_code="class TestSandboxSuite:\n    def setup(self): pass\n",
        source_hash="s2",
        start_byte=0,
        end_byte=80,
        start_line=5,
        end_line=15,
    )
    repo.upsert_brick(f2, sym2, portability_score=0.88, tags=["testing", "mock"])

    # 3. Rust async audio engine
    f3 = repo.upsert_source_file("repo-tools", "src/audio/engine.rs", "hash3", "rust")
    sym3 = ExtractedSymbol(
        symbol_name="AudioStreamEngine",
        qualified_name="audio.engine.AudioStreamEngine",
        kind="struct",
        language="rust",
        signature="pub struct AudioStreamEngine { buffer: Vec<f32> }",
        signature_hash="h3",
        docstring="High performance streaming audio synthesis engine in Rust.",
        source_code="pub struct AudioStreamEngine {\n    buffer: Vec<f32>,\n}\n",
        source_hash="s3",
        start_byte=0,
        end_byte=100,
        start_line=1,
        end_line=10,
    )
    repo.upsert_brick(f3, sym3, portability_score=0.98, tags=["audio", "rust", "dsp"])

    app = create_app(db_path=db_file)
    client = AppEndpointClient(app)
    return client, b1_id


@pytest.mark.unit
def test_get_index_html(test_web_client):
    client, _ = test_web_client
    response = client.get_index()
    assert response.status_code == 200
    html = response.body.decode("utf-8")
    assert "BRICKFORGE" in html
    assert "CATEGORIES" in html
    assert "brickExplorer" in html


@pytest.mark.unit
def test_get_stats(test_web_client):
    client, _ = test_web_client
    data = client.get_stats()
    assert data["total_bricks"] == 3
    assert data["total_files"] == 3
    assert data["total_repositories"] == 2
    assert data["by_kind"] == {"function": 1, "class": 1, "struct": 1}


@pytest.mark.unit
def test_get_categories(test_web_client):
    client, _ = test_web_client
    data = client.get_categories()
    assert data["total_bricks"] == 3

    # Check topic categorization
    topic_names = [t["name"] for t in data["topics"]]
    assert "AI & LLM / Agents" in topic_names
    assert "Testing & Benchmarks" in topic_names

    # Check kinds
    kind_names = [k["name"] for k in data["kinds"]]
    assert "function" in kind_names
    assert "class" in kind_names
    assert "struct" in kind_names

    # Check repositories
    repo_ids = [r["id"] for r in data["repositories"]]
    assert "repo-ai" in repo_ids
    assert "repo-tools" in repo_ids


@pytest.mark.unit
def test_search_bricks_default(test_web_client):
    client, _ = test_web_client
    data = client.search_bricks()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    # Verify field properties
    first = data["items"][0]
    assert "symbol_name" in first
    assert "signature" in first
    assert "portability_score" in first
    assert "topic" in first


@pytest.mark.unit
def test_search_bricks_with_filters(test_web_client):
    client, _ = test_web_client

    # 1. Search by query keyword
    res_q = client.search_bricks(query="prompt")
    items_q = res_q["items"]
    assert len(items_q) == 1
    assert items_q[0]["symbol_name"] == "generate_agent_prompt"

    # 2. Filter by topic
    res_topic = client.search_bricks(topic="AI & LLM / Agents")
    items_topic = res_topic["items"]
    assert len(items_topic) == 1
    assert items_topic[0]["symbol_name"] == "generate_agent_prompt"

    # 3. Filter by kind
    res_kind = client.search_bricks(kind="class")
    items_kind = res_kind["items"]
    assert len(items_kind) == 1
    assert items_kind[0]["symbol_name"] == "TestSandboxSuite"

    # 4. Filter by repo
    res_repo = client.search_bricks(repo="repo-tools")
    items_repo = res_repo["items"]
    assert len(items_repo) == 2
    assert all(i["repository_id"] == "repo-tools" for i in items_repo)


@pytest.mark.unit
def test_get_brick_detail(test_web_client):
    client, b1_id = test_web_client
    data = client.get_brick(b1_id)
    assert data["row_id"] == b1_id
    assert "generate_agent_prompt" in data["brick_id"]
    assert data["symbol_name"] == "generate_agent_prompt"
    assert "def generate_agent_prompt" in data["signature"]
    assert data["docstring"] == "Synthesize an agent system prompt from user instructions."
    assert "source_code" in data
    assert len(data["dependencies"]) == 1
    assert data["dependencies"][0]["package_name"] == "openai"


@pytest.mark.unit
def test_get_brick_detail_not_found(test_web_client):
    client, _ = test_web_client
    with pytest.raises(HTTPException) as exc_info:
        client.get_brick("non-existent-uuid")
    assert exc_info.value.status_code == 404


@pytest.mark.unit
def test_get_stats_projects_and_languages(test_web_client):
    client, _ = test_web_client
    data = client.get_stats()
    assert "total_projects" in data
    assert data["total_projects"] >= 2
    assert "by_language" in data
    assert "python" in data["by_language"]
    assert "top_projects" in data
    assert len(data["top_projects"]) >= 2
    for proj in data["top_projects"]:
        assert "ai_summary" in proj
        assert "file_count" in proj
        assert "brick_count" in proj


@pytest.mark.unit
def test_get_categories_languages_and_projects(test_web_client):
    client, _ = test_web_client
    data = client.get_categories()
    assert "languages" in data
    lang_codes = [l["code"] for l in data["languages"]]
    assert "py" in lang_codes

    assert "projects" in data
    assert len(data["projects"]) >= 2

    kind_names = [k["name"] for k in data["kinds"]]
    assert "project" in kind_names


@pytest.mark.unit
def test_search_bricks_by_language(test_web_client):
    client, _ = test_web_client
    res_py = client.search_bricks(language="py")
    assert res_py["total"] == 2
    for item in res_py["items"]:
        assert item["language_code"] == "py"
        assert item["project"] is not None

    # Test Rust by both code "rs" and full name "rust"
    res_rs = client.search_bricks(language="rs")
    assert res_rs["total"] == 1
    assert res_rs["items"][0]["symbol_name"] == "AudioStreamEngine"
    assert res_rs["items"][0]["language_code"] == "rs"

    res_rust = client.search_bricks(language="rust")
    assert res_rust["total"] == 1
    assert res_rust["items"][0]["symbol_name"] == "AudioStreamEngine"

    res_unknown = client.search_bricks(language="unknown_ext")
    assert res_unknown["total"] == 0


@pytest.mark.unit
def test_search_bricks_kind_project(test_web_client):
    client, _ = test_web_client
    res_proj = client.search_bricks(kind="project")
    assert res_proj["total"] >= 2
    for item in res_proj["items"]:
        assert item["kind"] == "project"
        assert "ai_summary" in item
        assert "file_count" in item
        assert "class_count" in item
        assert "function_count" in item


@pytest.mark.unit
def test_get_project_detail(test_web_client):
    client, _ = test_web_client
    # The fixture created repo-ai with file "agents/prompt_agent.py", project is "agents"
    proj_dossier = client.get_brick("project:repo-ai:agents")
    assert proj_dossier["kind"] == "project"
    assert proj_dossier["symbol_name"] == "agents"
    assert proj_dossier["repository_id"] == "repo-ai"
    assert "ai_summary" in proj_dossier
    assert "source_code" in proj_dossier
    assert "# PROJECT DOSSIER: agents" in proj_dossier["source_code"]
    assert len(proj_dossier["dependencies"]) >= 1


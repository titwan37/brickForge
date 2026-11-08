"""Unit tests for BrickForge Conversational Chat Engine and Ollama Grounding."""

from pathlib import Path
import pytest

from brickforge.parsers.base import ExtractedSymbol
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager
from brickforge.web.app import ChatRequest, create_app
from brickforge.web.chat import BrickForgeChatEngine, DEFAULT_MODEL


@pytest.fixture
def chat_fixture(tmp_path: Path):
    db_file = tmp_path / "test_chat.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('repo-media', 'Media Repo', '/media');")
        conn.commit()

    repo = BrickRepository(db_mgr)

    # 1. TTS Brick
    f1 = repo.upsert_source_file("repo-media", "skills/tts/generate_tts.py", "hash_tts", "python")
    sym1 = ExtractedSymbol(
        symbol_name="generate_tts_audio",
        qualified_name="skills.tts.generate_tts_audio",
        kind="function",
        language="python",
        signature="def generate_tts_audio(text: str, voice: str = 'en-US') -> bytes:",
        signature_hash="h_tts",
        docstring="Synthesize speech audio from text input using local engine.",
        source_code="def generate_tts_audio(text: str, voice: str = 'en-US') -> bytes:\n    # Synthesizes speech\n    return b'WAV_HEADER_DATA'\n",
        source_hash="s_tts",
        start_byte=0,
        end_byte=140,
        start_line=15,
        end_line=30,
    )
    b1_id = repo.upsert_brick(f1, sym1, portability_score=0.92, tags=["tts", "audio", "speech"])
    repo.insert_external_package(b1_id, "pip", "edge-tts", "import edge_tts")

    # 2. Audio Filter Brick
    sym2 = ExtractedSymbol(
        symbol_name="apply_audio_filter",
        qualified_name="skills.tts.apply_audio_filter",
        kind="function",
        language="python",
        signature="def apply_audio_filter(audio_bytes: bytes, effect: str) -> bytes:",
        signature_hash="h_filt",
        docstring="Apply telephone or DSP equalization filter to audio waveform.",
        source_code="def apply_audio_filter(audio_bytes: bytes, effect: str) -> bytes:\n    return audio_bytes\n",
        source_hash="s_filt",
        start_byte=0,
        end_byte=100,
        start_line=35,
        end_line=45,
    )
    repo.upsert_brick(f1, sym2, portability_score=1.0, tags=["audio", "filter", "dsp"])

    # 3. Markdown to PDF Converter Brick
    f2 = repo.upsert_source_file("repo-media", "scripts/convert_markdown_to_pdf.py", "hash_mdpdf", "python")
    sym3 = ExtractedSymbol(
        symbol_name="convert_markdown_to_pdf",
        qualified_name="scripts.convert_markdown_to_pdf",
        kind="function",
        language="python",
        signature="def convert_markdown_to_pdf(input_md: str, output_pdf: str) -> None:",
        signature_hash="h_mdpdf",
        docstring="Convert Markdown documentation and diagrams into styled PDF report.",
        source_code="def convert_markdown_to_pdf(input_md: str, output_pdf: str) -> None:\n    pass\n",
        source_hash="s_mdpdf",
        start_byte=0,
        end_byte=120,
        start_line=10,
        end_line=25,
    )
    repo.upsert_brick(f2, sym3, portability_score=0.96, tags=["markdown", "pdf", "convert"])

    engine = BrickForgeChatEngine(db_file)
    app = create_app(db_path=db_file)
    return engine, app, b1_id


@pytest.mark.unit
def test_search_catalog_for_tts(chat_fixture):
    engine, _, _ = chat_fixture
    # Query with 'tts' should retrieve generate_tts_audio and apply_audio_filter
    bricks = engine.search_catalog_for_query("How can I build a TTS audio pipeline?", limit=5)
    assert len(bricks) >= 1
    symbols = [b["symbol_name"] for b in bricks]
    assert "generate_tts_audio" in symbols

    tts_brick = next(b for b in bricks if b["symbol_name"] == "generate_tts_audio")
    assert tts_brick["repository_name"] == "Media Repo"
    assert "skills/tts/generate_tts.py" in tts_brick["relative_path"]
    assert tts_brick["start_line"] == 15
    assert tts_brick["end_line"] == 30
    assert tts_brick["portability_score"] == 0.92
    assert len(tts_brick["external_packages"]) == 1
    assert tts_brick["external_packages"][0]["name"] == "edge-tts"


@pytest.mark.unit
def test_search_catalog_for_markdown_pdf(chat_fixture):
    engine, _, _ = chat_fixture
    # Queries with adverbs like 'efficiently', 'all', and conversational fluff
    queries = [
        "Why my chat feedback is ignoring my own python script which are converting markdown to pdf",
        "how can i convert efficiently markdown to pdf ?",
        "what are all the function i have used to convert markdown to pdf ?",
    ]
    for q in queries:
        bricks = engine.search_catalog_for_query(q, limit=5)
        assert len(bricks) >= 1, f"Expected results for query: {q}"
        symbols = [b["symbol_name"] for b in bricks]
        assert "convert_markdown_to_pdf" in symbols, f"Missing convert_markdown_to_pdf in {symbols} for {q}"
        md_brick = next(b for b in bricks if b["symbol_name"] == "convert_markdown_to_pdf")
        assert md_brick["language"] == "python"
        assert "convert_markdown_to_pdf.py" in md_brick["relative_path"]
        assert md_brick["portability_score"] == 0.96


@pytest.mark.unit
def test_build_system_prompt(chat_fixture):
    engine, _, _ = chat_fixture
    bricks = engine.search_catalog_for_query("tts", limit=2)
    prompt = engine.build_system_prompt(bricks)
    assert "BrickForge Lead Software Architect" in prompt
    assert "generate_tts_audio" in prompt
    assert "skills/tts/generate_tts.py" in prompt
    assert "edge-tts" in prompt


@pytest.mark.unit
def test_generate_fallback_report(chat_fixture):
    engine, _, _ = chat_fixture
    bricks = engine.search_catalog_for_query("tts", limit=2)
    report = engine.generate_fallback_report("tts pipeline", bricks)
    assert "### 🧱 BrickForge Reusability Analysis" in report
    assert "`generate_tts_audio`" in report
    assert "skills/tts/generate_tts.py" in report
    assert "```python" in report


@pytest.mark.unit
def test_chat_execution(chat_fixture):
    engine, _, _ = chat_fixture
    messages = [{"role": "user", "content": "How do I implement TTS speech synthesis?"}]
    # Calling chat with Ollama offline should gracefully return grounded report
    result = engine.chat(messages, model="qwen2.5-coder:7b")
    assert "reply" in result
    assert len(result["bricks"]) >= 1
    assert "generate_tts_audio" in [b["symbol_name"] for b in result["bricks"]]
    assert result["bricks"][0]["relative_path"] == "skills/tts/generate_tts.py"
    assert "qwen2.5-coder:7b" in result["model_used"]
    assert "perf" in result
    assert result["perf"]["retrieval_ms"] >= 0
    assert result["perf"]["total_sec"] >= 0


@pytest.mark.unit
def test_chat_api_endpoints(chat_fixture):
    _, app, _ = chat_fixture
    route_map = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}

    # 1. GET /api/chat/models
    models_res = route_map["/api/chat/models"]()
    assert "models" in models_res
    assert DEFAULT_MODEL in models_res["models"]

    # 2. POST /api/chat
    req = ChatRequest(message="Can you advise on audio bricks for TTS?", history=[], model=DEFAULT_MODEL)
    chat_res = route_map["/api/chat"](req)
    assert "reply" in chat_res
    assert len(chat_res["bricks"]) >= 1
    assert any("tts" in b["symbol_name"].lower() for b in chat_res["bricks"])

    # 3. Stream verification
    messages = [{"role": "user", "content": "How do I implement TTS speech synthesis?"}]
    engine, _, _ = chat_fixture
    chunks = list(engine.chat_stream(messages, model=DEFAULT_MODEL))
    assert len(chunks) >= 3
    assert chunks[0]["type"] == "start"
    assert "bricks" in chunks[0]
    assert "retrieval_ms" in chunks[0]
    assert any(c["type"] == "token" for c in chunks)
    assert chunks[-1]["type"] == "done"
    assert "perf" in chunks[-1]
    assert chunks[-1]["perf"]["retrieval_ms"] >= 0
    assert chunks[-1]["perf"]["total_sec"] >= 0

    # 4. POST /api/chat/stream route
    stream_res = route_map["/api/chat/stream"](req)
    assert stream_res is not None
    assert stream_res.media_type == "text/event-stream"

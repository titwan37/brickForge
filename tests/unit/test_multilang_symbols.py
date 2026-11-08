"""Unit tests for MultiLanguageSymbolExtractor."""

from pathlib import Path
import pytest

from brickforge.parsers.multilang_symbols import MultiLanguageSymbolExtractor
from brickforge.parsers.tree_sitter_runtime import TreeSitterRuntime
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager
from brickforge.ingestion.pipeline import IngestionPipeline


@pytest.mark.unit
def test_csharp_symbol_extraction():
    cs_code = b"""
    using System;

    namespace Audio.Synthesis
    {
        /// <summary>
        /// Text to speech synthesis processor.
        /// </summary>
        public class SpeechProcessor : IDisposable
        {
            public int SampleRate { get; set; }

            public SpeechProcessor(int rate)
            {
                this.SampleRate = rate;
            }

            public async void SynthesizeAudio(string text)
            {
                await System.Threading.Tasks.Task.Delay(10);
            }
        }

        public interface ISpeechDevice
        {
            void Output(byte[] samples);
        }
    }
    """
    ts_runtime = TreeSitterRuntime()
    extractor = MultiLanguageSymbolExtractor(ts_runtime)
    assert extractor.can_extract("csharp")

    symbols, report = extractor.extract_symbols(cs_code, "csharp", "SpeechProcessor.cs")
    assert report.parse_status == "ok"
    assert len(symbols) >= 3

    names = [s.symbol_name for s in symbols]
    assert "SpeechProcessor" in names
    assert "SynthesizeAudio" in names
    assert "ISpeechDevice" in names

    proc = next(s for s in symbols if s.symbol_name == "SpeechProcessor" and s.kind == "class")
    assert proc.kind == "class"
    assert proc.language == "csharp"
    assert "Text to speech synthesis processor" in (proc.docstring or "")

    synth = next(s for s in symbols if s.symbol_name == "SynthesizeAudio")
    assert synth.kind == "method"
    assert synth.is_async is True


@pytest.mark.unit
def test_typescript_symbol_extraction():
    ts_code = b"""
    export interface AgentOptions {
        model: string;
        temperature: number;
    }

    export class CodeReviewAgent {
        private model: string;

        constructor(opts: AgentOptions) {
            this.model = opts.model;
        }

        public async reviewDiff(diff: string): Promise<string[]> {
            return ["Issue 1"];
        }
    }

    export const createAgent = (opts: AgentOptions): CodeReviewAgent => {
        return new CodeReviewAgent(opts);
    };
    """
    ts_runtime = TreeSitterRuntime()
    extractor = MultiLanguageSymbolExtractor(ts_runtime)
    assert extractor.can_extract("typescript")

    symbols, report = extractor.extract_symbols(ts_code, "typescript", "agent.ts")
    assert report.parse_status == "ok"
    assert len(symbols) >= 3

    names = [s.symbol_name for s in symbols]
    assert "AgentOptions" in names
    assert "CodeReviewAgent" in names
    assert "reviewDiff" in names
    assert "createAgent" in names


@pytest.mark.unit
def test_pipeline_multilang_integration(tmp_path: Path):
    db_file = tmp_path / "test_multilang.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('vs-test', 'VS Test', '/dummy');")
        conn.commit()

    repo = BrickRepository(db_mgr)
    pipeline = IngestionPipeline("vs-test", repo)

    cs_code = b"public class DataModel { public void Process() {} }"
    file_id, report, brick_ids = pipeline.process_file_content("models/DataModel.cs", cs_code)

    assert report.parse_status == "ok"
    assert len(brick_ids) >= 2

    # Query source_files
    sf = repo.get_source_file_by_path("vs-test", "models/DataModel.cs")
    assert sf is not None
    assert sf["language"] == "csharp"
    assert sf["parse_status"] == "ok"

    # Query bricks
    with db_mgr.connection() as conn:
        bricks = conn.execute("SELECT symbol_name, kind, language FROM code_bricks WHERE file_id = ?;", (file_id,)).fetchall()
        assert len(bricks) >= 2
        brick_names = [b[0] for b in bricks]
        assert "DataModel" in brick_names
        assert "Process" in brick_names
        assert bricks[0][2] == "csharp"


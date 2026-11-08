"""Initiative aggregation, persistence, and taxonomy classification for BrickForge."""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

INITIATIVES_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "ini_agentic_dev",
        "slug": "autonomous-agents-orchestration",
        "name": "Autonomous Agents & Multi-Agent Coding",
        "tagline": "Multi-agent coding loops, AST-grounded review, tool bridges, and LLM harness architecture.",
        "icon": "bot",
        "color_accent": "emerald",
        "display_order": 10,
        "keywords": [
            "agent", "codbot", "harness", "orchestrator", "worktree", "mcp", "patch",
            "autonomous", "prompt", "llm", "pipeline", "cordis", "activity", "worker",
            "brickforge", "agentic", "subagent", "qwen", "deepseek"
        ],
    },
    {
        "id": "ini_legaltech",
        "slug": "legaltech-procedural-intelligence",
        "name": "Sovereign LegalTech & Procedural Intelligence",
        "tagline": "Swiss statutory law retrieval, procedural exhibit generation, and case file evidence analysis.",
        "icon": "scale",
        "color_accent": "sky",
        "display_order": 20,
        "keywords": [
            "legal", "law", "swisslex", "fedlex", "avocat", "gericht", "acroform", "kesb",
            "socialdienst", "preuv", "auskunft", "justice", "juridique", "dossier", "chf",
            "alv", "rav", "lexpopuli", "lexibot"
        ],
    },
    {
        "id": "ini_audio_dsp",
        "slug": "audio-dsp-speech-intelligence",
        "name": "Speech, Voice & Audio Intelligence (DSP)",
        "tagline": "Spatial 3D audio, Whisper transcription, vocal biomarker diagnostics, and speech analytics.",
        "icon": "waveform",
        "color_accent": "amber",
        "display_order": 30,
        "keywords": [
            "voice", "audio", "dsp", "sound", "whisper", "speech", "transcri", "spatial",
            "biomarker", "acoustic", "vad", "music", "lyrics", "spotify", "radio", "tts",
            "dictaphone", "audacity"
        ],
    },
    {
        "id": "ini_doc_engineering",
        "slug": "document-intelligence-publishing",
        "name": "Document Intelligence & Zero-Loss Publishing",
        "tagline": "ALCOA+ document vaulting, high-precision PDF manipulations, and automated XeLaTeX typesetting.",
        "icon": "file-text",
        "color_accent": "indigo",
        "display_order": 40,
        "keywords": [
            "pdf", "latex", "xelatex", "markdown", "document", "publisher", "doc", "scan",
            "renamer", "convert", "report", "compress", "weasyprint", "typst", "latexfactory",
            "reposcroller", "pdfparadies"
        ],
    },
    {
        "id": "ini_vision_creative",
        "slug": "generative-media-computer-vision",
        "name": "Generative Creative Media & Computer Vision",
        "tagline": "GPU-accelerated image browsers, comics storyboard DAGs, and local diffusion engines.",
        "icon": "palette",
        "color_accent": "rose",
        "display_order": 50,
        "keywords": [
            "photo", "image", "gallery", "bild", "blitz", "aurabily", "flux", "monet",
            "omnigen", "diffus", "vision", "comics", "storyboard", "poem", "versecraft",
            "bitmap", "hyperframes", "video", "animation"
        ],
    },
    {
        "id": "ini_lowlevel_telemetry",
        "slug": "lowlevel-systems-telemetry-robotics",
        "name": "Low-Level Systems, Telemetry & Performance",
        "tagline": "Win32 handle monitoring, Chromium process diagnostics, C++ microservices, and robotics.",
        "icon": "cpu",
        "color_accent": "purple",
        "display_order": 60,
        "keywords": [
            "memory", "process", "simulacrum", "wmi", "hook", "win32", "thermal", "cpu",
            "robotics", "vacuum", "mova", "telemetry", "hardware", "network", "ping",
            "harness", "thread", "benchmark"
        ],
    },
    {
        "id": "ini_fintech_analytics",
        "slug": "fintech-stress-analytics",
        "name": "FinTech & Financial Stress Analytics",
        "tagline": "Bank transaction parsing, Swiss PostFinance data pipelines, and cost forecasting.",
        "icon": "coins",
        "color_accent": "teal",
        "display_order": 70,
        "keywords": [
            "finance", "banking", "postfinance", "apex", "transaction", "expense", "crypto",
            "trading", "freqtrade", "bitcoin", "budget", "invoice", "cashflow", "financial"
        ],
    },
    {
        "id": "ini_career_ops",
        "slug": "career-operations-logistics",
        "name": "Career Operations & Personal Logistics",
        "tagline": "Targeted dossier generation, life-admin automation, task graphs, and career management.",
        "icon": "briefcase",
        "color_accent": "orange",
        "display_order": 80,
        "keywords": [
            "career", "job", "apply", "candidate", "resume", "curriculum", "concierge",
            "task", "agenda", "rav", "employer", "worktime", "trello", "jobapply", "jobagentapply"
        ],
    },
]

INITIATIVES_BY_ID = {ini["id"]: ini for ini in INITIATIVES_REGISTRY}
INITIATIVES_BY_SLUG = {ini["slug"]: ini for ini in INITIATIVES_REGISTRY}


def ensure_initiatives_schema(conn: sqlite3.Connection) -> None:
    """Create initiatives tables and populate baseline registry if missing."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS initiatives (
            id TEXT PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            tagline TEXT NOT NULL,
            description TEXT,
            icon TEXT DEFAULT 'folder-kanban',
            color_accent TEXT DEFAULT 'indigo',
            display_order INTEGER DEFAULT 100,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS initiative_projects (
            initiative_id TEXT NOT NULL REFERENCES initiatives(id) ON DELETE CASCADE,
            project_key TEXT NOT NULL,
            is_primary INTEGER DEFAULT 1,
            relevance_score REAL DEFAULT 1.0,
            assigned_by TEXT DEFAULT 'rule',
            assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (initiative_id, project_key)
        );
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_initiative_projects_proj ON initiative_projects(project_key);"
    )

    # Populate / update registry definitions
    for ini in INITIATIVES_REGISTRY:
        cursor.execute(
            """
            INSERT INTO initiatives (id, slug, name, tagline, description, icon, color_accent, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                slug = excluded.slug,
                name = excluded.name,
                tagline = excluded.tagline,
                icon = excluded.icon,
                color_accent = excluded.color_accent,
                display_order = excluded.display_order;
            """,
            (
                ini["id"],
                ini["slug"],
                ini["name"],
                ini["tagline"],
                ini.get("description", ini["tagline"]),
                ini["icon"],
                ini["color_accent"],
                ini["display_order"],
            ),
        )
    conn.commit()


def classify_project_initiative(
    project_name: str,
    summary: str,
    heaviest_files: Optional[List[str]] = None,
    inferred_concepts: Optional[List[str]] = None,
) -> Tuple[str, float]:
    """
    Score a project against all defined strategic initiatives based on
    name tokens, intent summary text, filenames, and extracted concepts.
    Returns (initiative_id, confidence_score).
    """
    p_lower = (project_name or "").lower().strip()
    search_corpus = " ".join([
        project_name,
        p_lower,
        summary or "",
        " ".join(heaviest_files or []),
        " ".join(inferred_concepts or []),
    ]).lower()

    # Fast heuristics for well-known projects
    if any(k in p_lower for k in ["swisslex", "lawsuite", "legal", "urgence", "kesb", "socialdienst", "lexpopuli"]):
        return "ini_legaltech", 0.95
    if any(k in p_lower for k in ["voice", "audio", "whisper", "speech", "dictaphone", "sound", "biomarker"]):
        return "ini_audio_dsp", 0.95
    if any(k in p_lower for k in ["pdf", "latex", "publisher", "reposcroller", "markdown-publisher"]):
        return "ini_doc_engineering", 0.95
    if any(k in p_lower for k in ["aurabily", "flux", "monet", "bildblitz", "photo", "image", "hyperframes", "versecraft"]):
        return "ini_vision_creative", 0.92
    if any(k in p_lower for k in ["postfinance", "apex-analytics", "freqtrade", "bitcoin", "banking", "finance"]):
        return "ini_fintech_analytics", 0.95
    if any(k in p_lower for k in ["jobapply", "jobagentapply", "career", "resume", "concierge"]):
        return "ini_career_ops", 0.95
    if any(k in p_lower for k in ["memoryblast", "simulacrum", "mova", "telemetry", "win32", "robotics"]):
        return "ini_lowlevel_telemetry", 0.92
    if any(k in p_lower for k in ["codbot", "ecc", "deepseek-harness", "brickforge", "agent"]):
        return "ini_agentic_dev", 0.95

    best_initiative_id = "ini_agentic_dev"
    best_score = 0.0

    for ini in INITIATIVES_REGISTRY:
        score = 0.0
        for kw in ini["keywords"]:
            # Exact word boundary hits get higher weight
            matches = len(re.findall(rf"\b{re.escape(kw)}", search_corpus))
            if matches > 0:
                score += matches * 1.5
            elif kw in search_corpus:
                score += 0.8

        # Prioritize explicit project name matches
        for kw in ini["keywords"]:
            if kw in p_lower:
                score += 5.0

        if score > best_score:
            best_score = score
            best_initiative_id = ini["id"]

    confidence = min(1.0, round(best_score / 10.0, 2)) if best_score > 0 else 0.2
    return best_initiative_id, confidence


def get_all_initiatives_with_rollups(
    conn: sqlite3.Connection,
    projects: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Aggregate project metrics into high-level strategic initiative cards and ensure persistence.
    """
    ensure_initiatives_schema(conn)

    # Build initiative accumulator index
    initiatives_map = {
        ini["id"]: {
            "id": ini["id"],
            "slug": ini["slug"],
            "name": ini["name"],
            "tagline": ini["tagline"],
            "description": ini.get("description", ini["tagline"]),
            "icon": ini["icon"],
            "color_accent": ini["color_accent"],
            "display_order": ini["display_order"],
            "project_count": 0,
            "total_projects": 0,
            "total_files": 0,
            "total_bricks": 0,
            "total_classes": 0,
            "total_functions": 0,
            "languages": set(),
            "language_badges": set(),
            "projects": [],
        }
        for ini in INITIATIVES_REGISTRY
    }

    cursor = conn.cursor()
    # Batch upsert mapping
    mapping_records = []

    # Group projects into initiatives
    for proj in projects:
        p_name = proj.get("symbol_name") or ""
        repo_id = proj.get("repository_id") or ""
        project_key = f"{repo_id}:{p_name}"
        summary = proj.get("docstring") or proj.get("ai_summary") or ""

        ini_id, conf = classify_project_initiative(p_name, summary)
        target = initiatives_map.get(ini_id, initiatives_map["ini_agentic_dev"])

        # Tag back on the project dictionary for downstream consumer convenience
        proj["initiative_id"] = target["id"]
        proj["initiative_name"] = target["name"]
        proj["initiative_icon"] = target["icon"]
        proj["initiative_color"] = target["color_accent"]

        target["project_count"] += 1
        target["total_projects"] += 1
        target["total_files"] += proj.get("file_count", 0)
        target["total_bricks"] += proj.get("brick_count", 0)
        target["total_classes"] += proj.get("class_count", 0)
        target["total_functions"] += (proj.get("function_count", 0) + proj.get("method_count", 0))

        for lang in proj.get("languages", []):
            target["languages"].add(lang)
        for badge in proj.get("language_badges", []):
            target["language_badges"].add(badge)

        target["projects"].append({
            "name": p_name,
            "project_key": project_key,
            "brick_id": proj.get("brick_id"),
            "repository_id": repo_id,
            "repository_name": proj.get("repository_name", repo_id),
            "file_count": proj.get("file_count", 0),
            "brick_count": proj.get("brick_count", 0),
            "language": proj.get("language", "python"),
            "language_code": proj.get("language_code", "py"),
            "summary": summary[:160] + "..." if len(summary) > 160 else summary,
            "confidence": conf,
        })

        mapping_records.append((target["id"], project_key, 1, conf, "rule"))

    # Persist assignments
    if mapping_records:
        cursor.executemany(
            """
            INSERT INTO initiative_projects (initiative_id, project_key, is_primary, relevance_score, assigned_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(initiative_id, project_key) DO UPDATE SET
                relevance_score = excluded.relevance_score,
                is_primary = excluded.is_primary;
            """,
            mapping_records,
        )
        conn.commit()

    result = []
    for ini in sorted(initiatives_map.values(), key=lambda x: x["display_order"]):
        ini["languages"] = sorted(list(ini["languages"]))
        ini["language_badges"] = sorted(list(ini["language_badges"]))
        # Sort member projects by brick count descending
        ini["projects"].sort(key=lambda x: x["brick_count"], reverse=True)
        result.append(ini)

    return result


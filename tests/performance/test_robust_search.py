import sqlite3
import re
from typing import List, Dict, Any, Optional

conn = sqlite3.connect('C:/Dev/brickForge/data/brickforge.db')
conn.row_factory = sqlite3.Row

# Comprehensive conversational query stopwords (extended with adverbs, adjectives, question fluff)
QUERY_STOPWORDS = {
    # Standard English stopwords
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and',
    'any', 'are', 'aren', 'as', 'at', 'be', 'because', 'been', 'before', 'being',
    'below', 'between', 'both', 'but', 'by', 'can', 'cannot', 'could', 'did', 'do',
    'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had',
    'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself', 'him', 'himself',
    'his', 'how', 'i', 'if', 'in', 'into', 'is', 'isn', 'it', 'its', 'itself', 'let',
    'me', 'more', 'most', 'my', 'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once',
    'only', 'or', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own',
    'same', 'she', 'should', 'so', 'some', 'such', 'than', 'that', 'the', 'their',
    'theirs', 'them', 'themselves', 'then', 'there', 'these', 'they', 'this', 'those',
    'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what',
    'when', 'where', 'which', 'while', 'who', 'whom', 'why', 'with', 'would', 'you',
    'your', 'yours', 'yourself', 'yourselves',
    # Conversational chat wrapper words
    'tell', 'show', 'find', 'give', 'suggest', 'recommend', 'advise', 'consult',
    'look', 'search', 'get', 'fetch', 'list', 'please', 'help', 'want', 'need',
    'code', 'script', 'scripts', 'brick', 'bricks', 'component', 'components',
    'module', 'modules', 'file', 'files', 'function', 'functions', 'class', 'classes',
    'method', 'methods', 'example', 'examples', 'feedback', 'ignoring', 'ignored',
    'spontaneously', 'refer', 'refers', 'referring', 'related', 'implement', 'implementation',
    # Common question adverbs, adjectives and intent fluff
    'efficiently', 'quickly', 'easily', 'directly', 'properly', 'best', 'good', 'simple',
    'fast', 'all', 'used', 'using', 'use', 'way', 'ways', 'solution', 'solutions',
    'different', 'various', 'able', 'currently', 'actually', 'really', 'possible', 'like',
    'available', 'better', 'great', 'right', 'know', 'try', 'trying'
}

THEME_EXPANSIONS = {
    "tts": ["tts", "speech", "audio", "voice", "sound", "synthesize", "speaker"],
    "audio": ["audio", "sound", "wave", "dsp", "voice", "speech", "tts"],
    "speech": ["speech", "voice", "tts", "audio", "transcribe", "stt"],
    "agent": ["agent", "llm", "prompt", "pipeline", "orchestrator", "tool"],
    "auth": ["auth", "token", "jwt", "login", "password", "signature", "verify"],
    "database": ["db", "sql", "sqlite", "postgres", "query", "storage", "repository"],
    "test": ["test", "mock", "fixture", "suite", "runner", "assert"],
    "parser": ["parser", "ast", "tree", "token", "lexer", "grammar"],
    "markdown": ["markdown", "md"],
    "md": ["md", "markdown"],
    "pdf": ["pdf"],
    "convert": ["convert", "converter", "compile", "transform", "export", "render", "extract"]
}

LANG_MAP = {
    "python": "python",
    "py": "python",
    "typescript": "typescript",
    "ts": "typescript",
    "tsx": "typescript-react",
    "javascript": "javascript",
    "js": "javascript",
    "csharp": "csharp",
    "c#": "csharp",
    "rust": "rust",
    "rs": "rust",
    "go": "go",
    "golang": "go",
    "cpp": "cpp",
    "c++": "cpp"
}

def is_vendor_path(path: str) -> bool:
    p = path.lower()
    vendor_markers = ["jquery", "bootstrap", "node_modules", "vendor/", "site-packages", ".min.js", "dist/"]
    return any(m in p for m in vendor_markers)

def is_test_path(path: str, symbol: str) -> bool:
    p = path.lower()
    s = symbol.lower()
    return ("/test" in p or "tests/" in p or s.startswith("test_") or "_test." in p)

def detect_language_intent(query: str) -> Optional[str]:
    q_lower = query.lower()
    for pattern, lang in LANG_MAP.items():
        if re.search(r"(?:^|[\s_\-/,.])" + re.escape(pattern) + r"(?:$|[\s_\-/,.])", q_lower):
            return lang
    return None

def robust_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    lang_pref = detect_language_intent(query)
    raw_tokens = [t.lower() for t in re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", query)]
    core_tokens = [t for t in raw_tokens if t not in QUERY_STOPWORDS]
    if not core_tokens:
        core_tokens = [t for t in raw_tokens if t not in {'a', 'an', 'the', 'to', 'in', 'of', 'for', 'is', 'on', 'at'}]
    if not core_tokens:
        core_tokens = raw_tokens

    results: List[Dict[str, Any]] = []
    seen_ids = set()

    def add_rows(rows, max_count=limit):
        dict_rows = [dict(r) for r in rows]
        sorted_rows = sorted(
            dict_rows,
            key=lambda r: (
                1 if is_vendor_path(r["relative_path"]) else 0,
                1 if is_test_path(r["relative_path"], r["symbol_name"]) else 0,
                0 if (lang_pref and r.get("language") == lang_pref) else 1,
                r.get("rank", 0) if r.get("rank") is not None else 0,
                -float(r.get("portability_score") or 0.0),
            ),
        )
        for r in sorted_rows:
            bid = r["row_id"]
            if bid not in seen_ids:
                results.append(r)
                seen_ids.add(bid)
                if len(results) >= max_count:
                    break

    # Check for domain pairs: e.g. markdown and pdf
    is_md_pdf = ('markdown' in core_tokens or 'md' in core_tokens) and ('pdf' in core_tokens)
    if is_md_pdf:
        fts_pair = '("markdown"* OR "md"*) AND "pdf"*'
        sql_pair = """
        SELECT b.row_id, b.id AS brick_id, b.symbol_name, b.kind, b.language,
               b.signature, b.docstring, b.portability_score, s.relative_path, f.rank
        FROM bricks_fts f
        JOIN code_bricks b ON f.rowid = b.row_id
        JOIN source_files s ON b.file_id = s.row_id
        WHERE bricks_fts MATCH ?
        ORDER BY f.rank ASC
        LIMIT 20;
        """
        rows = conn.execute(sql_pair, (fts_pair,)).fetchall()
        add_rows(rows)

    # Strategy 1: FTS5 AND with top core tokens
    if len(results) < limit and len(core_tokens) >= 2:
        and_fts = ' AND '.join(f'"{t}"*' for t in core_tokens[:4])
        try:
            sql = """
            SELECT b.row_id, b.id AS brick_id, b.symbol_name, b.kind, b.language,
                   b.signature, b.docstring, b.portability_score, s.relative_path, f.rank
            FROM bricks_fts f
            JOIN code_bricks b ON f.rowid = b.row_id
            JOIN source_files s ON b.file_id = s.row_id
            WHERE bricks_fts MATCH ?
            ORDER BY f.rank ASC
            LIMIT 20;
            """
            rows = conn.execute(sql, (and_fts,)).fetchall()
            add_rows(rows)
        except Exception:
            pass

    # Strategy 2: BM25 OR with expanded terms
    if len(results) < limit:
        expanded_terms = list(core_tokens)
        for t in core_tokens:
            if t in THEME_EXPANSIONS:
                for exp in THEME_EXPANSIONS[t]:
                    if exp not in expanded_terms:
                        expanded_terms.append(exp)
        if expanded_terms:
            or_fts = ' OR '.join(f'"{t}"*' for t in expanded_terms[:8])
            try:
                sql_or = """
                SELECT b.row_id, b.id AS brick_id, b.symbol_name, b.kind, b.language,
                       b.signature, b.docstring, b.portability_score, s.relative_path, f.rank
                FROM bricks_fts f
                JOIN code_bricks b ON f.rowid = b.row_id
                JOIN source_files s ON b.file_id = s.row_id
                WHERE bricks_fts MATCH ?
                ORDER BY f.rank ASC
                LIMIT 25;
                """
                rows = conn.execute(sql_or, (or_fts,)).fetchall()
                add_rows(rows)
            except Exception:
                pass

    return results

queries = [
    "how can i convert efficiently markdown to pdf ?",
    "what are all the function i have used to convert markdown to pdf ?",
    "how to convert markdown to pdf",
    "convert md to pdf"
]

for q in queries:
    print(f"\n==================== Query: {q} ====================")
    res = robust_search(q, limit=5)
    print(f"Results ({len(res)}):")
    for r in res:
        print(f"  [{r['language']}] {r['symbol_name']} ({r['kind']}) -> {r['relative_path']}")

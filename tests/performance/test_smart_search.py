import sqlite3
import re
from typing import List, Dict, Any, Optional

conn = sqlite3.connect('C:/Dev/brickForge/data/brickforge.db')
conn.row_factory = sqlite3.Row

QUERY_STOPWORDS = {
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
    'tell', 'show', 'find', 'give', 'suggest', 'recommend', 'advise', 'consult',
    'look', 'search', 'get', 'fetch', 'list', 'please', 'help', 'want', 'need',
    'code', 'script', 'scripts', 'brick', 'bricks', 'component', 'components',
    'module', 'modules', 'file', 'files', 'function', 'functions', 'class', 'classes',
    'method', 'methods', 'example', 'examples', 'feedback', 'ignoring', 'ignored',
    'spontaneously', 'refer', 'refers', 'referring', 'related', 'implement', 'implementation'
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

def detect_language(query: str) -> Optional[str]:
    q_lower = query.lower()
    for pattern, lang in LANG_MAP.items():
        if re.search(r'(?:^|[\s_\-/,.])' + re.escape(pattern) + r'(?:$|[\s_\-/,.])', q_lower):
            return lang
    return None

def is_vendor_file(path: str) -> bool:
    p = path.lower()
    vendor_markers = ['jquery', 'bootstrap', 'node_modules', 'vendor/', 'site-packages', '.min.js', 'dist/']
    return any(m in p for m in vendor_markers)

def smart_search(query: str, limit: int = 5):
    lang_pref = detect_language(query)
    raw_tokens = [t.lower() for t in re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", query)]
    core_tokens = [t for t in raw_tokens if t not in QUERY_STOPWORDS]
    if not core_tokens:
        core_tokens = raw_tokens

    expanded_terms = list(core_tokens)
    for t in core_tokens:
        if t in THEME_EXPANSIONS:
            for exp in THEME_EXPANSIONS[t]:
                if exp not in expanded_terms:
                    expanded_terms.append(exp)

    results: List[Dict[str, Any]] = []
    seen_ids = set()

    def add_rows(rows, max_count=limit):
        dict_rows = [dict(r) for r in rows]
        sorted_rows = sorted(
            dict_rows,
            key=lambda r: (
                1 if is_vendor_file(r['relative_path']) else 0,
                0 if (lang_pref and r['language'] == lang_pref) else 1,
                r.get('rank', 0) if r.get('rank') is not None else 0
            )
        )
        for r in sorted_rows:
            rid = r['row_id']
            if rid not in seen_ids:
                results.append(r)
                seen_ids.add(rid)
                if len(results) >= max_count:
                    break

    # Tier 1: FTS5 AND with top core tokens
    if len(core_tokens) >= 2:
        and_fts = ' AND '.join(f'"{t}"*' for t in core_tokens[:4])
        try:
            sql = '''
            SELECT b.row_id, b.id AS brick_id, b.symbol_name, b.kind, b.language,
                   b.portability_score, s.relative_path, f.rank
            FROM bricks_fts f
            JOIN code_bricks b ON f.rowid = b.row_id
            JOIN source_files s ON b.file_id = s.row_id
            WHERE bricks_fts MATCH ?
            ORDER BY f.rank ASC
            LIMIT 15;
            '''
            rows = conn.execute(sql, (and_fts,)).fetchall()
            add_rows(rows)
        except Exception as e:
            pass

    # Tier 2: FTS5 BM25 OR with expanded tokens
    if len(results) < limit and expanded_terms:
        or_fts = ' OR '.join(f'"{t}"*' for t in expanded_terms[:8])
        try:
            sql_or = '''
            SELECT b.row_id, b.id AS brick_id, b.symbol_name, b.kind, b.language,
                   b.portability_score, s.relative_path, f.rank
            FROM bricks_fts f
            JOIN code_bricks b ON f.rowid = b.row_id
            JOIN source_files s ON b.file_id = s.row_id
            WHERE bricks_fts MATCH ?
            ORDER BY f.rank ASC
            LIMIT 20;
            '''
            rows = conn.execute(sql_or, (or_fts,)).fetchall()
            add_rows(rows)
        except Exception as e:
            pass

    # Tier 3: SQL LIKE fallback
    if len(results) < limit:
        like_conds = []
        params = []
        for t in core_tokens[:4]:
            like_conds.append("(b.symbol_name LIKE ? OR s.relative_path LIKE ? OR b.docstring LIKE ?)")
            wild = f"%{t}%"
            params.extend([wild, wild, wild])
        if like_conds:
            sql_like = f'''
            SELECT b.row_id, b.id AS brick_id, b.symbol_name, b.kind, b.language,
                   b.portability_score, s.relative_path, 0.0 AS rank
            FROM code_bricks b
            JOIN source_files s ON b.file_id = s.row_id
            WHERE ({' OR '.join(like_conds)})
            ORDER BY b.portability_score DESC
            LIMIT 10;
            '''
            rows = conn.execute(sql_like, params).fetchall()
            add_rows(rows)

    return results

test_queries = [
    "Why my chat feedback is ignoring my own python script which are converting markdown to pdf",
    "markdown to pdf",
    "Markdown to PDF Conversion",
    "convert md to color pdf",
    "How can I build a TTS or speech pipeline from our indexed bricks?",
    "Find reusable token, JWT, and authentication handlers"
]

for q in test_queries:
    print(f"\n==================== Query: {q} ====================")
    res = smart_search(q, limit=5)
    print(f"Results ({len(res)}):")
    for r in res:
        print(f"  [{r['language']}] {r['symbol_name']} ({r['kind']}) -> {r['relative_path']}")

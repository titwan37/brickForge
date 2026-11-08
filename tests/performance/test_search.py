import sqlite3
import re

conn = sqlite3.connect('C:/Dev/brickForge/data/brickforge.db')
conn.row_factory = sqlite3.Row

# Comprehensive conversational query stopwords
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
    "convert": ["convert", "converter", "compile", "transform", "export", "render"]
}

def extract_core_keywords(query: str):
    raw_tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z0-9_\-]{2,}\b', query)]
    filtered = [t for t in raw_tokens if t not in QUERY_STOPWORDS]
    # If all tokens were stopwords, keep raw tokens
    tokens = filtered if filtered else raw_tokens
    
    # Expand domain terms
    expanded = list(tokens)
    for t in tokens:
        if t in THEME_EXPANSIONS:
            for exp in THEME_EXPANSIONS[t]:
                if exp not in expanded:
                    expanded.append(exp)
    return tokens, expanded

queries = [
    'markdown to pdf',
    'Markdown to PDF Conversion',
    'Why my chat feedback is ignoring my own python script which are converting markdown to pdf',
    'convert md to color pdf',
    'How do I implement TTS speech synthesis?',
]

for q in queries:
    print(f"\n==================== Query: {q} ====================")
    core_tokens, expanded_tokens = extract_core_keywords(q)
    print("Core tokens:", core_tokens)
    print("Expanded:", expanded_tokens[:6])
    
    # Strategy 1: All core tokens with AND (or first 2-3 most specific)
    results = []
    if len(core_tokens) >= 2:
        and_clause = ' AND '.join(f'"{t}"*' for t in core_tokens[:3])
        sql = '''
        SELECT b.row_id, b.symbol_name, b.kind, b.language, s.relative_path, f.rank, b.portability_score
        FROM bricks_fts f
        JOIN code_bricks b ON f.rowid = b.row_id
        JOIN source_files s ON b.file_id = s.row_id
        WHERE bricks_fts MATCH ?
        ORDER BY f.rank ASC, b.portability_score DESC
        LIMIT 5
        '''
        results = conn.execute(sql, (and_clause,)).fetchall()
        print(f"AND clause ({and_clause}) returned:", len(results))
    
    # Strategy 2: If < 5 results, search using expanded tokens with BM25 rank
    if len(results) < 5:
        existing_ids = {r['row_id'] for r in results}
        or_clause = ' OR '.join(f'"{t}"*' for t in expanded_tokens[:6])
        sql_or = '''
        SELECT b.row_id, b.symbol_name, b.kind, b.language, s.relative_path, f.rank, b.portability_score
        FROM bricks_fts f
        JOIN code_bricks b ON f.rowid = b.row_id
        JOIN source_files s ON b.file_id = s.row_id
        WHERE bricks_fts MATCH ?
        ORDER BY f.rank ASC, b.portability_score DESC
        LIMIT 10
        '''
        or_rows = conn.execute(sql_or, (or_clause,)).fetchall()
        for r in or_rows:
            if r['row_id'] not in existing_ids:
                results.append(r)
                existing_ids.add(r['row_id'])
                if len(results) >= 5:
                    break

    for r in results[:5]:
        print("  ->", r['symbol_name'], "|", r['language'], "|", r['relative_path'], "| rank:", round(r['rank'], 2))

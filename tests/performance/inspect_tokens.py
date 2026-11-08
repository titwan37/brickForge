import re
import sqlite3
from brickforge.web.chat import QUERY_STOPWORDS, THEME_EXPANSIONS

query = 'how can i convert efficiently markdown to pdf ?'
raw_tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z0-9_\-]{2,}\b', query)]
core_tokens = [t for t in raw_tokens if t not in QUERY_STOPWORDS]
print('raw_tokens:', raw_tokens)
print('core_tokens:', core_tokens)

conn = sqlite3.connect('C:/Dev/brickForge/data/brickforge.db')
conn.row_factory = sqlite3.Row

# What did Strategy 1 run?
and_query_str = ' AND '.join(f'"{t}"*' for t in core_tokens[:4])
print('Strategy 1 AND query:', and_query_str)
rows1 = conn.execute('''
    SELECT b.row_id, b.symbol_name, s.relative_path, f.rank
    FROM bricks_fts f
    JOIN code_bricks b ON f.rowid = b.row_id
    JOIN source_files s ON b.file_id = s.row_id
    WHERE bricks_fts MATCH ?
    ORDER BY f.rank ASC
    LIMIT 10;
''', (and_query_str,)).fetchall()
print('Strategy 1 matches:', len(rows1))
for r in rows1:
    print(' ', r['symbol_name'], '->', r['relative_path'], r['rank'])

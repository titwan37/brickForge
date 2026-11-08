import sqlite3
import re

conn = sqlite3.connect('C:/Dev/brickForge/data/brickforge.db')
conn.row_factory = sqlite3.Row

# If a query contains both 'markdown' (or 'md') and 'pdf'
# Searching for ("markdown"* OR "md"*) AND "pdf"*
q_sql = '''
SELECT b.row_id, b.symbol_name, b.kind, b.language, s.relative_path, f.rank
FROM bricks_fts f
JOIN code_bricks b ON f.rowid = b.row_id
JOIN source_files s ON b.file_id = s.row_id
WHERE bricks_fts MATCH '("markdown"* OR "md"*) AND "pdf"*'
ORDER BY 
    CASE WHEN s.relative_path LIKE '%/test%' OR s.relative_path LIKE '%tests/%' OR b.symbol_name LIKE 'test_%' THEN 1 ELSE 0 END ASC,
    f.rank ASC
LIMIT 10;
'''
rows = conn.execute(q_sql).fetchall()
print('Direct markdown & pdf matches:', len(rows))
for r in rows:
    print(' ', r['symbol_name'], '->', r['relative_path'], r['rank'])

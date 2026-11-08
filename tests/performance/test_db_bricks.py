import sqlite3

conn = sqlite3.connect("C:/Dev/brickForge/data/brickforge.db")
cursor = conn.cursor()
q = """
SELECT b.id, b.symbol_name, b.kind, b.signature, s.relative_path, b.portability_score, b.docstring
FROM code_bricks b
JOIN source_files s ON b.file_id = s.row_id
WHERE s.relative_path LIKE '%audio%' 
   OR s.relative_path LIKE '%tts%' 
   OR s.relative_path LIKE '%speech%'
   OR b.symbol_name LIKE '%audio%' 
   OR b.symbol_name LIKE '%speech%'
   OR b.symbol_name LIKE '%tts%'
LIMIT 12;
"""
rows = cursor.execute(q).fetchall()
print(f"Found {len(rows)} bricks:")
for r in rows:
    print(f"- {r[1]} ({r[2]}) at {r[4]} | Portability: {r[5]}")

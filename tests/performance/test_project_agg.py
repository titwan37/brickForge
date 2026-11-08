import sqlite3
from pathlib import Path

conn = sqlite3.connect("C:/Dev/brickForge/data/brickforge.db")
cursor = conn.cursor()

# Query project aggregation
query = """
SELECT 
    s.repository_id,
    CASE 
        WHEN INSTR(s.relative_path, '/') > 0 THEN SUBSTR(s.relative_path, 1, INSTR(s.relative_path, '/') - 1)
        WHEN INSTR(s.relative_path, '\\') > 0 THEN SUBSTR(s.relative_path, 1, INSTR(s.relative_path, '\\') - 1)
        ELSE 'root'
    END AS project_name,
    COUNT(DISTINCT s.row_id) AS file_count,
    COUNT(b.row_id) AS brick_count,
    SUM(CASE WHEN b.kind = 'class' THEN 1 ELSE 0 END) AS class_count,
    SUM(CASE WHEN b.kind = 'function' THEN 1 ELSE 0 END) AS func_count,
    SUM(CASE WHEN b.kind = 'method' THEN 1 ELSE 0 END) AS method_count,
    ROUND(AVG(b.portability_score), 2) AS avg_portability
FROM source_files s
LEFT JOIN code_bricks b ON b.file_id = s.row_id
GROUP BY s.repository_id, project_name
HAVING brick_count > 0
ORDER BY brick_count DESC
LIMIT 15;
"""

rows = cursor.execute(query).fetchall()
print(f"Top 15 Projects with indexed bricks:")
for r in rows:
    print(f"- Repo: {r[0]} | Project: {r[1]} | Files: {r[2]} | Bricks: {r[3]} (Classes: {r[4]}, Funcs: {r[5]}, Methods: {r[6]}) | Avg P: {r[7]}")

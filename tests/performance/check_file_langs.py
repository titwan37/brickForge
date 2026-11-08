import sqlite3
from pathlib import Path

conn = sqlite3.connect("C:/Dev/brickForge/data/brickforge.db")
cursor = conn.cursor()

query = """
SELECT 
    CASE 
        WHEN relative_path LIKE '%.py' THEN 'python'
        WHEN relative_path LIKE '%.ts' THEN 'typescript'
        WHEN relative_path LIKE '%.tsx' THEN 'typescript-react'
        WHEN relative_path LIKE '%.js' THEN 'javascript'
        WHEN relative_path LIKE '%.jsx' THEN 'javascript-react'
        WHEN relative_path LIKE '%.cs' THEN 'csharp'
        WHEN relative_path LIKE '%.cpp' OR relative_path LIKE '%.c' OR relative_path LIKE '%.h' OR relative_path LIKE '%.hpp' THEN 'cpp'
        WHEN relative_path LIKE '%.json' THEN 'json'
        WHEN relative_path LIKE '%.md' THEN 'markdown'
        WHEN relative_path LIKE '%.html' THEN 'html'
        WHEN relative_path LIKE '%.css' THEN 'css'
        WHEN relative_path LIKE '%.sql' THEN 'sql'
        ELSE 'other'
    END AS ext_lang,
    COUNT(*) as cnt
FROM source_files
GROUP BY ext_lang
ORDER BY cnt DESC;
"""

for r in cursor.execute(query):
    print(r)

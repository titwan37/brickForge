import sqlite3

conn = sqlite3.connect("C:/Dev/brickForge/data/brickforge.db")
cursor = conn.cursor()

# Languages in code_bricks and source_files
print("Languages in code_bricks:")
for r in cursor.execute("SELECT language, COUNT(*) FROM code_bricks GROUP BY language"):
    print(r)

print("\nLanguages in source_files:")
for r in cursor.execute("SELECT language, COUNT(*) FROM source_files GROUP BY language"):
    print(r)

# Check projects under dev-c
print("\nTop paths in dev-c:")
query = """
SELECT 
    CASE 
        WHEN INSTR(relative_path, '/') > 0 THEN SUBSTR(relative_path, 1, INSTR(relative_path, '/') - 1)
        WHEN INSTR(relative_path, '\\') > 0 THEN SUBSTR(relative_path, 1, INSTR(relative_path, '\\') - 1)
        ELSE 'root'
    END AS project_name,
    COUNT(row_id) AS file_count
FROM source_files
WHERE repository_id = 'dev-c'
GROUP BY project_name
ORDER BY file_count DESC
LIMIT 25;
"""
for r in cursor.execute(query):
    print(r)

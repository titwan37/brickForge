import sqlite3

conn = sqlite3.connect("C:/Dev/brickForge/data/brickforge.db")
cursor = conn.cursor()

for repo in ['gdrive-work-code', 'gdrive-legalstudio', 'onedrive-vscode']:
    print(f"\nRepo: {repo}")
    query = f"""
    SELECT 
        CASE 
            WHEN INSTR(relative_path, '/') > 0 THEN SUBSTR(relative_path, 1, INSTR(relative_path, '/') - 1)
            ELSE relative_path
        END AS proj,
        COUNT(*) as cnt
    FROM source_files
    WHERE repository_id = '{repo}'
    GROUP BY proj
    ORDER BY cnt DESC
    LIMIT 10;
    """
    for r in cursor.execute(query):
        print(" ", r)

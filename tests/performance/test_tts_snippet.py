import sqlite3

conn = sqlite3.connect("C:/Dev/brickForge/data/brickforge.db")
cursor = conn.cursor()
q = "SELECT symbol_name, signature, start_line, end_line, source_code FROM code_bricks WHERE symbol_name = 'generate_tts_single' LIMIT 1"
row = cursor.execute(q).fetchone()
if row:
    print("Symbol:", row[0])
    print("Signature:", row[1])
    print(f"Lines: {row[2]}-{row[3]}")
    print("Source snippet:\n", "\n".join(row[4].splitlines()[:15]))

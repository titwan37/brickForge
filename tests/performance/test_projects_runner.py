import sqlite3
from brickforge.web.projects import get_all_projects

conn = sqlite3.connect("C:/Dev/brickForge/data/brickforge.db")
conn.row_factory = sqlite3.Row
projs = get_all_projects(conn)
print(f"Total projects found: {len(projs)}")
for p in projs[:5]:
    print(f"- {p['symbol_name']} [{p['repository_id']}]:")
    print(f"  Files: {p['file_count']} | Bricks: {p['brick_count']} (Classes: {p['class_count']}, Funcs: {p['function_count']}, Methods: {p['method_count']})")
    print(f"  Languages: {p['languages']} ({p['language_badges']})")
    print(f"  AI Intent: {p['ai_summary'][:100]}...\n")

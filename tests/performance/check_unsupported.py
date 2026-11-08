import sqlite3
import os
from collections import defaultdict

conn = sqlite3.connect(r"C:\Dev\brickForge\data\brickforge.db")
c = conn.cursor()

rows = c.execute("SELECT repository_id, relative_path FROM source_files WHERE parse_status = 'unsupported'").fetchall()
exts_by_repo = defaultdict(lambda: defaultdict(int))
total_exts = defaultdict(int)

for repo_id, path in rows:
    ext = os.path.splitext(path)[1].lower()
    exts_by_repo[repo_id][ext] += 1
    total_exts[ext] += 1

print("--- Overall Top 20 Unsupported Extensions ---")
for ext, count in sorted(total_exts.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f"  {ext or '[no-ext]'}: {count}")

print("\n--- Extensions in VS Repositories ---")
for repo_id in ["vs-2010", "vs-2012", "vs-2015", "vs-2019", "onedrive-vscode"]:
    if repo_id in exts_by_repo:
        print(f"\n{repo_id}:")
        for ext, count in sorted(exts_by_repo[repo_id].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {ext or '[no-ext]'}: {count}")

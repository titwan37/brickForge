"""
[('c', 267), ('cpp', 2), ('csharp', 15657), ('javascript', 26154), ('python', 70971), ('rust', 16026), ('typescript', 27829), ('typescript-react', 3318)]
"""
import sqlite3
conn = sqlite3.connect(r'C:\Dev\brickForge\data\brickforge.db')
print(conn.execute('SELECT language, count(*) FROM code_bricks GROUP BY language').fetchall())


import time, sqlite3; from pathlib import Path
from brickforge.web.app import TOPIC_SQL_EXPR, TOPIC_ICONS
from brickforge.web.projects import get_all_projects, normalize_language_badge
conn = sqlite3.connect(r'C:\Dev\brickForge\data\brickforge.db')
conn.row_factory = sqlite3.Row
t0 = time.time();
cursor = conn.cursor()
cursor.execute(f'SELECT {TOPIC_SQL_EXPR} AS topic, COUNT(b.row_id) as count FROM code_bricks b JOIN source_files s ON b.file_id = s.row_id GROUP BY topic ORDER BY count DESC;'); topics = cursor.fetchall(); print(f'1. Topics: {time.time()-t0:.2f}s'); t1 = time.time();
projects = get_all_projects(conn); print(f'2. Projects: {time.time()-t1:.2f}s'); t2 = time.time();
cursor.execute('SELECT kind, COUNT(*) as count FROM code_bricks GROUP BY kind ORDER BY count DESC;'); kinds = cursor.fetchall(); print(f'3. Kinds: {time.time()-t2:.2f}s'); t3 = time.time();
cursor.execute('SELECT r.id, r.name, COUNT(b.row_id) as count FROM repositories r LEFT JOIN source_files s ON s.repository_id = r.id LEFT JOIN code_bricks b ON b.file_id = s.row_id GROUP BY r.id, r.name ORDER BY count DESC;'); repos = cursor.fetchall(); print(f'4. Repos: {time.time()-t3:.2f}s'); t4 = time.time();
cursor.execute('SELECT language, COUNT(*) as count FROM code_bricks GROUP BY language ORDER BY count DESC;'); langs = [{'name': r['language'], 'code': normalize_language_badge(r['language']), 'count': r['count']} for r in cursor.fetchall()]; print(f'5. Langs: {time.time()-t4:.2f}s');
print('Done in', time.time()-t0, 'Langs:', langs)
import json
from brickforge.web.app import create_app

app = create_app()
routes = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}

print("=== 1. Test /api/stats ===")
stats = routes["/api/stats"]()
print(f"Total Projects: {stats.get('total_projects')}")
print(f"By Language: {stats.get('by_language')}")
print(f"Top 2 Projects: {[p['project_name'] for p in stats.get('top_projects', [])[:2]]}")

print("\n=== 2. Test /api/categories ===")
cats = routes["/api/categories"]()
print(f"Languages: {cats.get('languages')}")
print(f"Kinds: {cats.get('kinds')}")
print(f"Projects in categories: {len(cats.get('projects', []))}")

print("\n=== 3. Test /api/bricks?kind=project ===")
projs = routes["/api/bricks"](kind="project", page=1, page_size=3)
print(f"Total projects: {projs['total']}")
for p in projs["items"]:
    print(f" - {p['symbol_name']} [{p['repository_id']}]: {p['file_count']} files, {p['brick_count']} bricks (C:{p['class_count']}, F:{p['function_count']}, M:{p['method_count']})")
    print(f"   Intent: {p['ai_summary'][:90]}...")

print("\n=== 4. Test /api/bricks?language=py ===")
bricks_py = routes["/api/bricks"](language="py", page=1, page_size=2)
print(f"Total py bricks: {bricks_py['total']}")
for b in bricks_py["items"]:
    print(f" - {b['symbol_name']} | lang: {b['language']} ({b['language_code']}) | project: {b.get('project')}")

print("\n=== 5. Test /api/brick/{brick_id} for a project ===")
proj_detail = routes["/api/brick/{brick_id}"](brick_id="project:dev-c:codbot3")
print(f"Symbol: {proj_detail['symbol_name']} | Kind: {proj_detail['kind']}")
print(f"Files: {proj_detail['file_count']} | Bricks: {proj_detail['brick_count']} (C:{proj_detail['class_count']}, F:{proj_detail['function_count']}, M:{proj_detail['method_count']})")
print(f"Intent: {proj_detail['ai_summary'][:100]}...")
print(f"Contained Bricks: {len(proj_detail['dependencies'])}")

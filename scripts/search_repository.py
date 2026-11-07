from pathlib import Path
from brickforge.storage.database import DatabaseManager
from brickforge.search.service import CatalogSearchService, CatalogQuery

db_mgr = DatabaseManager(db_path=Path("data/brickforge.db"))
search = CatalogSearchService(db_mgr)

# Search across all 8 repositories
hits = search.search(CatalogQuery(query="UserService", limit=10))
for hit in hits:
    print(f"{hit.symbol_name} ({hit.kind}) in [{hit.repository_id}] {hit.relative_path}")
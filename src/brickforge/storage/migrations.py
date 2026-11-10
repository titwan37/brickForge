from __future__ import annotations

import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

DEFAULT_BUSY_TIMEOUT_MS = 5000
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

class Migration(migrations.Migration):

    dependencies = [
        ('storage', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE TABLE IF NOT EXISTS document_sources (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, path TEXT NOT NULL, heading_hierarchy TEXT, line_ranges TEXT, content_hash TEXT, citations TEXT);",
            reverse_sql="DROP TABLE IF EXISTS document_sources;",
        ),
        migrations.RunSQL(
            "CREATE TABLE IF NOT EXISTS document_chunks (id TEXT PRIMARY KEY, document_source_id TEXT NOT NULL, heading TEXT, line_ranges TEXT, content_hash TEXT, citations TEXT, FOREIGN KEY (document_source_id) REFERENCES document_sources(id));",
            reverse_sql="DROP TABLE IF EXISTS document_chunks;",
        ),
        migrations.RunSQL(
            "CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(id, document_source_id, heading, line_ranges, content_hash, citations);",
            reverse_sql="DROP TABLE IF EXISTS document_chunks_fts;",
        ),
    ]

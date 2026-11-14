import unittest
from unittest.mock import patch

from brickforge.storage.database import DatabaseManager
from brickforge.storage.document_repository import DocumentRepository
from brickforge.storage.document_models import DocumentSource, DocumentChunk

class TestDocumentRepository(unittest.TestCase):
    @patch.object(DatabaseManager, '__init__', return_value=None)
    def setUp(self, mock_db_manager):
        self.db_manager = DatabaseManager()
        self.repository = DocumentRepository(self.db_manager)

    def test_add_document_source(self):
        document_source = DocumentSource(
            id="123",
            project_id="project1",
            path="path/to/document",
            heading_hierarchy="heading1",
            line_ranges="1-10",
            content_hash="hash1",
            citations=[],
        )
        self.repository.add_document_source(document_source)
        with self.db_manager.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM document_sources WHERE id = ?;",
                (document_source.id,),
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], document_source.id)
            self.assertEqual(row[1], document_source.project_id)
            self.assertEqual(row[2], document_source.path)
            self.assertEqual(row[3], document_source.heading_hierarchy)
            self.assertEqual(row[4], document_source.line_ranges)
            self.assertEqual(row[5], document_source.content_hash)
            self.assertEqual(row[6], document_source.citations)

    def test_add_document_chunk(self):
        document_chunk = DocumentChunk(
            id="456",
            document_source_id="123",
            heading="heading2",
            line_ranges="11-20",
            content_hash="hash2",
            citations=[],
        )
        self.repository.add_document_chunk(document_chunk)
        with self.db_manager.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM document_chunks WHERE id = ?;",
                (document_chunk.id,),
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], document_chunk.id)
            self.assertEqual(row[1], document_chunk.document_source_id)
            self.assertEqual(row[2], document_chunk.heading)
            self.assertEqual(row[3], document_chunk.line_ranges)
            self.assertEqual(row[4], document_chunk.content_hash)
            self.assertEqual(row[5], document_chunk.citations)

    def test_get_document_source(self):
        document_source = DocumentSource(
            id="123",
            project_id="project1",
            path="path/to/document",
            heading_hierarchy="heading1",
            line_ranges="1-10",
            content_hash="hash1",
            citations=[],
        )
        self.repository.add_document_source(document_source)
        retrieved_source = self.repository.get_document_source(document_source.id)
        self.assertIsNotNone(retrieved_source)
        self.assertEqual(retrieved_source.id, document_source.id)
        self.assertEqual(retrieved_source.project_id, document_source.project_id)
        self.assertEqual(retrieved_source.path, document_source.path)
        self.assertEqual(retrieved_source.heading_hierarchy, document_source.heading_hierarchy)
        self.assertEqual(retrieved_source.line_ranges, document_source.line_ranges)
        self.assertEqual(retrieved_source.content_hash, document_source.content_hash)
        self.assertEqual(retrieved_source.citations, document_source.citations)

    def test_get_document_chunk(self):
        document_chunk = DocumentChunk(
            id="456",
            document_source_id="123",
            heading="heading2",
            line_ranges="11-20",
            content_hash="hash2",
            citations=[],
        )
        self.repository.add_document_chunk(document_chunk)
        retrieved_chunk = self.repository.get_document_chunk(document_chunk.id)
        self.assertIsNotNone(retrieved_chunk)
        self.assertEqual(retrieved_chunk.id, document_chunk.id)
        self.assertEqual(retrieved_chunk.document_source_id, document_chunk.document_source_id)
        self.assertEqual(retrieved_chunk.heading, document_chunk.heading)
        self.assertEqual(retrieved_chunk.line_ranges, document_chunk.line_ranges)
        self.assertEqual(retrieved_chunk.content_hash, document_chunk.content_hash)
        self.assertEqual(retrieved_chunk.citations, document_chunk.citations)

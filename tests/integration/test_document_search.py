from unittest.mock import patch

from brickforge.storage.database import DatabaseManager
from brickforge.search.document_search import DocumentSearchService
from brickforge.storage.document_models import DocumentChunk

class TestDocumentSearchService:
    @patch('src.brickforge.storage.database.DatabaseManager.create_connection')
    def test_search(self, mock_create_connection):
        mock_conn = mock_create_connection.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchall.return_value = [
            ('chunk1', 'source1', 'Heading 1', '1-10', 'hash1', 'cite1'),
            ('chunk2', 'source2', 'Heading 2', '11-20', 'hash2', 'cite2'),
        ]

        db_manager = DatabaseManager()
        service = DocumentSearchService(db_manager)
        results = service.search('query')

        assert len(results) == 2
        assert results[0].id == 'chunk1'
        assert results[1].id == 'chunk2'

    @patch('src.brickforge.storage.database.DatabaseManager.create_connection')
    def test_upsert_chunk(self, mock_create_connection):
        mock_conn = mock_create_connection.return_value

        db_manager = DatabaseManager()
        service = DocumentSearchService(db_manager)
        chunk = DocumentChunk(
            id='chunk1',
            document_source_id='source1',
            heading='Heading 1',
            line_ranges='1-10',
            content_hash='hash1',
            citations='cite1',
        )
        service.upsert_chunk(chunk)

        mock_conn.execute.assert_called()

    @patch('src.brickforge.storage.database.DatabaseManager.create_connection')
    def test_delete_chunk(self, mock_create_connection):
        mock_conn = mock_create_connection.return_value

        db_manager = DatabaseManager()
        service = DocumentSearchService(db_manager)
        service.delete_chunk('chunk1')

        mock_conn.execute.assert_called()

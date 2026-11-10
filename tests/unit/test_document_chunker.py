from unittest import TestCase
from unittest.mock import patch

from src.brickforge.ingestion.document_chunker import DocumentChunker
from src.brickforge.storage.document_models import DocumentSource, Citation

class TestDocumentChunker(TestCase):

    def setUp(self):
        self.document_source = DocumentSource(
            id="doc1",
            project_id="proj1",
            path="path/to/doc.md",
            content_hash="hash1",
            citations=[Citation(source_id="src1", line_number=1)]
        )
        self.chunker = DocumentChunker()

    @patch.object(DocumentChunker, '_calculate_content_hash', return_value='mock_hash')
    def test_chunk_document(self, mock_hash):
        self.document_source.content = "# Heading 1\nThis is a test document.\n## Heading 2\nMore content here."
        chunks = self.chunker.chunk_document(self.document_source)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].heading, "Heading 1")
        self.assertEqual(chunks[1].heading, "Heading 2")
        self.assertEqual(chunks[0].line_ranges, "1-2")
        self.assertEqual(chunks[1].line_ranges, "3-4")

    @patch.object(DocumentChunker, '_calculate_content_hash', return_value='mock_hash')
    def test_large_chunk_splitting(self, mock_hash):
        self.document_source.content = "A" * 2500
        self.chunker.max_chunk_size = 1000
        self.chunker.overlap_size = 200
        chunks = self.chunker.chunk_document(self.document_source)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].line_ranges, "1-10")
        self.assertEqual(chunks[1].line_ranges, "9-18")
        self.assertEqual(chunks[2].line_ranges, "17-25")

    @patch.object(DocumentChunker, '_calculate_content_hash', return_value='mock_hash')
    def test_no_headings(self, mock_hash):
        self.document_source.content = "This is a test document without headings."
        chunks = self.chunker.chunk_document(self.document_source)
        self.assertEqual(len(chunks), 1)
        self.assertIsNone(chunks[0].heading)
        self.assertEqual(chunks[0].line_ranges, "1-1")

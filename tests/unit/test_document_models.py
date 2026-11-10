import unittest
from unittest.mock import patch

from src.brickforge.storage.document_models import Citation, DocumentSource, DocumentChunk

class TestDocumentSource(unittest.TestCase):
    def test_document_source_model(self):
        source = DocumentSource(
            id="source1",
            project_id="project1",
            path="path/to/document",
            content_hash="hash1",
            citations=[Citation(source_id="citation1")]
        )
        self.assertEqual(source.id, "source1")
        self.assertEqual(source.project_id, "project1")
        self.assertEqual(source.path, "path/to/document")
        self.assertEqual(source.content_hash, "hash1")
        self.assertEqual(len(source.citations), 1)

class TestDocumentChunk(unittest.TestCase):
    def test_document_chunk_model(self):
        chunk = DocumentChunk(
            id="chunk1",
            document_source_id="source1",
            content_hash="hash1",
            citations=[Citation(source_id="citation1")]
        )
        self.assertEqual(chunk.id, "chunk1")
        self.assertEqual(chunk.document_source_id, "source1")
        self.assertEqual(chunk.content_hash, "hash1")
        self.assertEqual(len(chunk.citations), 1)

from unittest.mock import patch, MagicMock
from brickforge.search.project_retrieval import ProjectRetrievalService, ProjectEvidence
from brickforge.search.service import CatalogSearchHit, CatalogQuery
from brickforge.search.document_search import DocumentChunk

def test_search():
    mock_db = MagicMock()
    mock_catalog_search_service = MagicMock()
    mock_document_search_service = MagicMock()

    mock_catalog_search_service.search.return_value = [
        CatalogSearchHit(
            brick_id="brick1",
            symbol_name="symbol1",
            qualified_name="qualified1",
            kind="kind1",
            language="language1",
            signature="signature1",
            docstring="docstring1",
            relative_path="path1",
            repository_id="repo1",
            portability_score=0.85,
        )
    ]

    mock_document_search_service.search.return_value = [
        DocumentChunk(
            id="doc1",
            document_source_id="source1",
            heading="heading1",
            line_ranges="1-10",
            content_hash="hash1",
            citations="citation1",
        )
    ]

    with patch('src.brickforge.search.project_retrieval.CatalogSearchService', return_value=mock_catalog_search_service):
        with patch('src.brickforge.search.project_retrieval.DocumentSearchService', return_value=mock_document_search_service):
            service = ProjectRetrievalService(mock_db)
            query_params = CatalogQuery(query="test", repository_id="repo1")
            results = service.search(query_params)

    assert len(results) == 2
    assert results[0].source_type == "brick"
    assert results[0].repository_id == "repo1"
    assert results[0].path == "path1"
    assert results[0].line_range == "N/A"
    assert results[0].excerpt == "signature1"
    assert results[0].stable_citation_id == "brick1"

    assert results[1].source_type == "document"
    assert results[1].repository_id == "source1"
    assert results[1].path == "N/A"
    assert results[1].line_range == "1-10"
    assert results[1].excerpt == "hash1"
    assert results[1].stable_citation_id == "doc1"

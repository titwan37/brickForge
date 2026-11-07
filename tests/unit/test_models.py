import pytest
from pydantic import ValidationError

from src.brickforge.models.repository import Repository
from src.brickforge.models.scan import (
    ScanRun,
    ScanStatus,
    SourceFileMetadata,
    Exclusion,
    ScanError,
)


def test_repository_model():
    repo = Repository(id='1', name='test_repo', url='http://test.com', last_scan_id=None)
    assert repo.id == '1'
    assert repo.name == 'test_repo'
    assert repo.url == 'http://test.com'
    assert repo.last_scan_id is None


def test_repository_model_missing_required_fields():
    with pytest.raises(ValidationError):
        Repository(name='test_repo', url='http://test.com')


def test_scan_run_model():
    scan = ScanRun(
        id='scan-1',
        repository_id='repo-1',
        start_time='2023-01-01T00:00:00Z',
        end_time=None,
        status='running'
    )
    assert scan.id == 'scan-1'
    assert scan.repository_id == 'repo-1'
    assert scan.start_time == '2023-01-01T00:00:00Z'
    assert scan.end_time is None
    assert scan.status == 'running'


def test_scan_run_model_missing_required_fields():
    with pytest.raises(ValidationError):
        ScanRun(id='scan-1', repository_id='repo-1')


def test_scan_status_model():
    status = ScanStatus(
        id='status-1',
        scan_id='scan-1',
        message='Scan started',
        timestamp='2023-01-01T00:00:00Z'
    )
    assert status.id == 'status-1'
    assert status.scan_id == 'scan-1'
    assert status.message == 'Scan started'
    assert status.timestamp == '2023-01-01T00:00:00Z'


def test_scan_status_model_missing_required_fields():
    with pytest.raises(ValidationError):
        ScanStatus(id='status-1', scan_id='scan-1')


def test_source_file_metadata_model():
    meta = SourceFileMetadata(
        id='file-1',
        scan_id='scan-1',
        file_path='src/main.py',
        file_hash='abc123',
        file_size=1024
    )
    assert meta.id == 'file-1'
    assert meta.scan_id == 'scan-1'
    assert meta.file_path == 'src/main.py'
    assert meta.file_hash == 'abc123'
    assert meta.file_size == 1024


def test_source_file_metadata_model_missing_required_fields():
    with pytest.raises(ValidationError):
        SourceFileMetadata(id='file-1', scan_id='scan-1')


def test_exclusion_model():
    exclusion = Exclusion(
        id='excl-1',
        repository_id='repo-1',
        pattern='*.log'
    )
    assert exclusion.id == 'excl-1'
    assert exclusion.repository_id == 'repo-1'
    assert exclusion.pattern == '*.log'


def test_exclusion_model_missing_required_fields():
    with pytest.raises(ValidationError):
        Exclusion(id='excl-1', repository_id='repo-1')


def test_scan_error_model():
    error = ScanError(
        id='err-1',
        scan_id='scan-1',
        error_code='E001',
        error_message='Something went wrong',
        timestamp='2023-01-01T00:00:00Z'
    )
    assert error.id == 'err-1'
    assert error.scan_id == 'scan-1'
    assert error.error_code == 'E001'
    assert error.error_message == 'Something went wrong'
    assert error.timestamp == '2023-01-01T00:00:00Z'


def test_scan_error_model_missing_required_fields():
    with pytest.raises(ValidationError):
        ScanError(id='err-1', scan_id='scan-1')

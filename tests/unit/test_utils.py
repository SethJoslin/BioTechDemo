"""Unit tests for utility functions."""
import pytest
import uuid
from pathlib import Path
from fastapi import HTTPException

from app.utils import validate_uuid, validate_path_safe


@pytest.mark.unit
def test_validate_uuid_valid():
    """Test UUID validation with valid UUID."""
    valid_uuid = str(uuid.uuid4())
    # Should not raise
    validate_uuid(valid_uuid)


@pytest.mark.unit
def test_validate_uuid_invalid():
    """Test UUID validation with invalid UUID."""
    with pytest.raises(HTTPException) as exc_info:
        validate_uuid("not-a-uuid")

    assert exc_info.value.status_code == 400
    assert "Invalid UUID" in exc_info.value.detail


@pytest.mark.unit
def test_validate_uuid_empty():
    """Test UUID validation with empty string."""
    with pytest.raises(HTTPException):
        validate_uuid("")


@pytest.mark.unit
def test_validate_path_safe_clean_path():
    """Test path validation with clean path."""
    safe_path = "/data/runs/abc123/features.parquet"
    result = validate_path_safe(safe_path)
    # On Windows, Path.resolve() converts to absolute UNC paths
    # Check that the resolved path ends with expected components
    result_path = Path(result)
    assert result_path.name == "features.parquet"
    assert result_path.parent.name == "abc123"
    assert result_path.parts[-4] == "runs" or result_path.parts[-3] == "runs"


@pytest.mark.unit
def test_validate_path_safe_directory_traversal():
    """Test path validation rejects directory traversal."""
    dangerous_paths = [
        "/data/../../../etc/passwd",
        "/data/runs/../../secrets.txt",
        "~/../../etc/passwd",
        "/data/runs/../.ssh/id_rsa",
    ]

    for path in dangerous_paths:
        with pytest.raises(HTTPException) as exc_info:
            validate_path_safe(path)
        assert exc_info.value.status_code == 400
        assert "Invalid path" in exc_info.value.detail


@pytest.mark.unit
def test_validate_path_safe_environment_variables():
    """Test path validation rejects environment variable expansion."""
    dangerous_paths = [
        "/data/${SECRET}/file.txt",
        "/data/$(cat /etc/passwd)/file.txt",
    ]

    for path in dangerous_paths:
        with pytest.raises(HTTPException):
            validate_path_safe(path)


@pytest.mark.unit
def test_validate_path_safe_with_allowed_prefixes():
    """Test path validation with allowed prefix whitelist."""
    allowed = ["/data/runs", "/data/artifacts"]

    # Should pass - check path components rather than exact string
    safe = validate_path_safe("/data/runs/abc123/file.txt", allowed_prefixes=allowed)
    safe_path = Path(safe)
    assert safe_path.name == "file.txt"
    assert safe_path.parent.name == "abc123"
    assert "runs" in safe_path.parts

    # Should also pass
    safe = validate_path_safe("/data/artifacts/model.pt", allowed_prefixes=allowed)
    safe_path = Path(safe)
    assert safe_path.name == "model.pt"
    assert "artifacts" in safe_path.parts

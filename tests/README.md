# Testing Guide

## Overview

This project uses **pytest** with a 3-tier testing strategy:

```
Unit Tests (70%)       → Fast, isolated function tests
Integration Tests (25%) → API + DB interaction tests
E2E Tests (5%)         → Complete workflow tests
```

**Current Coverage Target**: 70% (increasing to 80%)

---

## Quick Start

```bash
# Install test dependencies
pip install -e "services/api/[test]"
pip install pytest pytest-cov pytest-mock

# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific categories
pytest -m unit              # Fast unit tests only
pytest -m integration       # Integration tests only
pytest -m "not slow"        # Skip slow E2E tests

# Run and generate HTML coverage report
pytest --cov --cov-report=html
open htmlcov/index.html
```

---

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_cellranger.py
│   ├── test_qc.py
│   ├── test_inference.py
│   └── test_utils.py
├── integration/             # Integration tests (API + DB)
│   ├── test_api_runs.py
│   ├── test_api_auth.py
│   └── test_api_viz.py
├── e2e/                     # End-to-end tests (slow)
│   └── test_full_pipeline.py
└── test_loader.py           # Snowflake integration tests
```

### Test Organization Convention

**For submodules and integrations (e.g., `snowflake_integration/`, `celery_tasks/`):**
- Tests belong in **root `tests/` folder**, named after the module (e.g., `test_loader.py`, `test_tasks.py`)
- Do NOT create separate `submodule/tests/` folders—this causes pytest discovery issues and duplicate files
- Exception: If a submodule becomes a standalone package with its own `setup.py`, move tests with it

**Why this matters:**
- Pytest discovers tests from a single root (`tests/`)
- Duplicate test files in multiple locations cause:
  - Tests silently not running (discovery issues)
  - Files diverging out of sync
  - Confusion about which version is canonical

---

## Test Categories & Markers

### Unit Tests (`@pytest.mark.unit`)
**Purpose**: Test individual functions in isolation
**Duration**: <1s per test
**Dependencies**: None (mocked)

```python
@pytest.mark.unit
def test_validate_uuid():
    """Test UUID validation."""
    validate_uuid("valid-uuid-here")
    # Should not raise
```

### Integration Tests (`@pytest.mark.integration`)
**Purpose**: Test component interactions (API + DB, API + ML)
**Duration**: 1-5s per test
**Dependencies**: Test database, FastAPI test client

```python
@pytest.mark.integration
def test_create_run(client, auth_headers):
    """Test creating a run via API."""
    response = client.post("/v1/runs", json={"name": "test"}, headers=auth_headers)
    assert response.status_code == 201
```

### E2E Tests (`@pytest.mark.e2e`, `@pytest.mark.slow`)
**Purpose**: Test complete user workflows
**Duration**: 5-30s per test
**Dependencies**: Full application stack

```python
@pytest.mark.e2e
@pytest.mark.slow
def test_complete_pipeline(client, auth_headers):
    """Test: create run → extract features → search similar."""
    ...
```

---

## Fixtures

All fixtures are defined in `conftest.py`:

| Fixture | Description | Scope |
|---------|-------------|-------|
| `test_db` | In-memory SQLite database | function |
| `client` | FastAPI test client | function |
| `auth_token` | JWT authentication token | function |
| `auth_headers` | Authorization headers dict | function |
| `sample_adata` | Mock AnnData (100 cells, 200 genes) | function |
| `sample_features` | Mock PCA features (100×50) | function |
| `sample_parquet` | Features saved as Parquet file | function |
| `mock_model_checkpoint` | Small PyTorch model for testing | function |
| `temp_dir` | Temporary directory (auto-cleaned) | function |

**Usage**:
```python
def test_something(sample_adata, temp_dir):
    # Use fixtures directly as function arguments
    assert sample_adata.n_obs == 100
    output_path = temp_dir / "output.h5ad"
    sample_adata.write_h5ad(output_path)
```

---

## Running Tests

### Run Everything
```bash
pytest
```

### Run by Category
```bash
pytest -m unit              # Unit tests only (fast)
pytest -m integration       # Integration tests
pytest -m "unit or integration"  # Both
pytest -m "not slow"        # Skip slow E2E tests
```

### Run by File/Function
```bash
pytest tests/unit/test_qc.py                    # Single file
pytest tests/unit/test_qc.py::test_compute_qc_metrics  # Single test
pytest -k "cellranger"                          # All tests matching "cellranger"
```

### With Coverage
```bash
pytest --cov                                    # Terminal report
pytest --cov --cov-report=html                  # HTML report
pytest --cov --cov-report=term-missing          # Show missing lines
```

### Parallel Execution
```bash
pip install pytest-xdist
pytest -n auto              # Use all CPU cores
pytest -n 4                 # Use 4 workers
```

### Debugging
```bash
pytest -s                   # Show print statements
pytest --pdb                # Drop into debugger on failure
pytest -x                   # Stop on first failure
pytest -vv                  # Very verbose output
```

---

## Writing New Tests

### 1. Unit Test Template

```python
import pytest

@pytest.mark.unit
def test_my_function():
    """Test my_function does X."""
    # Arrange
    input_data = ...

    # Act
    result = my_function(input_data)

    # Assert
    assert result == expected_value
```

### 2. Integration Test Template

```python
import pytest

@pytest.mark.integration
def test_api_endpoint(client, auth_headers):
    """Test /v1/endpoint returns correct data."""
    # Act
    response = client.post(
        "/v1/endpoint",
        json={"key": "value"},
        headers=auth_headers
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["key"] == "value"
```

### 3. E2E Test Template

```python
import pytest

@pytest.mark.e2e
@pytest.mark.slow
def test_workflow(client, auth_headers):
    """Test complete workflow."""
    # Step 1: Create resource
    response1 = client.post(...)
    resource_id = response1.json()["id"]

    # Step 2: Process resource
    response2 = client.post(f".../{resource_id}/process")
    assert response2.status_code == 202

    # Step 3: Verify result
    response3 = client.get(f".../{resource_id}")
    assert response3.json()["status"] == "completed"
```

---

## Coverage Goals

| Module | Target Coverage |
|--------|----------------|
| `services/api/app/routers/` | 85% |
| `services/api/app/ml/` | 80% |
| `lib/openbioops/models/` | 85% |
| `lib/openbioops/processing/` | 80% |
| `services/api/app/utils.py` | 90% |
| **Overall** | **70% → 80%** |

---

## CI Integration

Tests run automatically on every push via GitHub Actions:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: pytest --cov --cov-report=xml

- name: Check coverage
  run: |
    coverage report --fail-under=70
```

**CI will fail if**:
- Any test fails
- Coverage drops below 70%
- New code is added without tests

---

## Mocking Strategy

### External Services
Use `unittest.mock.patch` for external dependencies:

```python
from unittest import mock

@mock.patch('app.tasks.extract_features_task.delay')
def test_trigger_task(mock_task, client, auth_headers):
    mock_task.return_value = mock.Mock(id="task_123")

    response = client.post("/v1/runs/abc/features", headers=auth_headers)

    assert response.status_code == 202
    mock_task.assert_called_once()
```

### File I/O
Use `temp_dir` fixture:

```python
def test_save_file(temp_dir):
    output_path = temp_dir / "output.txt"
    save_file(output_path, "content")
    assert output_path.read_text() == "content"
```

### Database
Use `test_db` fixture (in-memory SQLite):

```python
def test_database_operation(test_db):
    from app.db import RunModel

    run = RunModel(id="123", name="test")
    test_db.add(run)
    test_db.commit()

    retrieved = test_db.query(RunModel).filter_by(id="123").first()
    assert retrieved.name == "test"
```

---

## Performance Benchmarks

Add performance assertions to catch regressions:

```python
@pytest.mark.benchmark
def test_inference_speed(benchmark, mock_model_checkpoint, sample_parquet):
    """Benchmark inference throughput."""
    model = load_encoder(mock_model_checkpoint)

    result = benchmark(embed_features, model, sample_parquet)

    # Assert minimum throughput
    cells_per_second = 100 / benchmark.stats.mean
    assert cells_per_second > 1000  # 1k cells/sec minimum
```

---

## Troubleshooting

### Import Errors
```bash
# Ensure packages are installed in editable mode
pip install -e lib/
pip install -e services/api/
```

### Fixture Not Found
```bash
# Check conftest.py is in the right location
# Fixtures must be in conftest.py or same file as test
```

### Database Locked
```bash
# Use in-memory database (already configured)
# Ensure each test gets fresh database via `test_db` fixture
```

### Tests Hang
```bash
# Add timeout to pytest
pytest --timeout=30
```

---

## Best Practices

1. **Test names should describe what they test**:
    `test_create_run_with_valid_data`
    `test1`

2. **One assertion per test** (when possible):
   ```python
   def test_validation_accepts_valid_uuid():
       validate_uuid("valid-uuid")  # Should not raise

   def test_validation_rejects_invalid_uuid():
       with pytest.raises(HTTPException):
           validate_uuid("invalid")
   ```

3. **Use fixtures over global setup**:
    `def test_foo(sample_data):`
    `sample_data = ...  # Global`

4. **Test behavior, not implementation**:
    `assert response.status_code == 200`
    `assert function_was_called_with_x()`

5. **Add tests for bug fixes**:
   ```python
   def test_bug_123_division_by_zero():
       """Regression test for bug #123."""
       result = calculate(x=0)
       assert result == 0  # Should not crash
   ```

---

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [Coverage.py Docs](https://coverage.readthedocs.io/)

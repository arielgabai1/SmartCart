# Backend Tests

## Overview

API and unit tests for the Smart Cart backend using pytest.

## Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run by priority
pytest -m p0          # Critical tests only
pytest -m "p0 or p1"  # P0 + P1 tests

# Run specific test file
pytest tests/api/test_health.py

# Run with verbose output
pytest -v
```

## Test Structure

```
tests/
├── api/                    # API integration tests
│   ├── test_health.py      # Health endpoint tests
│   └── test_items.py       # Items endpoint tests
├── unit/                   # Unit tests
├── support/
│   ├── fixtures/           # Test fixtures
│   └── factories/          # Data factories
├── conftest.py             # Shared fixtures
└── README.md
```

## Priority Tags

- **@p0**: Critical paths - run every commit
- **@p1**: High priority - run on PR
- **@p2**: Medium priority - run nightly
- **@p3**: Low priority - run on-demand

## Writing Tests

Follow Given-When-Then format:

```python
@pytest.mark.p1
@pytest.mark.api
def test_example(self, client):
    """[P1] Description of what is being tested.

    GIVEN: Initial state/preconditions
    WHEN: Action being tested
    THEN: Expected outcome
    """
    # Test implementation
```

## Factories

Use factories from `tests/support/factories/` for test data:

```python
from tests.support.factories.item_factory import create_item, create_items

item = create_item()
items = create_items(5, overrides={"status": "APPROVED"})
```

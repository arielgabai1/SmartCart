import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
from app import app as flask_app


class MockCollection:
    """Mock MongoDB collection for testing."""

    def __init__(self):
        self._items = []

    def find(self, filter=None):
        if filter is None:
            return list(self._items)
        return [i for i in self._items if all(i.get(k) == v for k, v in filter.items())]

    def find_one(self, filter):
        for item in self._items:
            match = True
            for k, v in filter.items():
                if k == '_id':
                    # Handle ObjectId comparison - compare string representations
                    if str(item.get('_id')) != str(v):
                        match = False
                        break
                elif item.get(k) != v:
                    match = False
                    break
            if match:
                return item.copy()
        return None

    def insert_one(self, document):
        doc = document.copy()
        doc['_id'] = ObjectId()
        self._items.append(doc)
        return MagicMock(inserted_id=doc['_id'])

    def update_one(self, filter, update):
        for item in self._items:
            match = True
            for k, v in filter.items():
                if k == '_id':
                    if str(item.get('_id')) != str(v):
                        match = False
                        break
                elif item.get(k) != v:
                    match = False
                    break
            if match:
                for key, value in update.get('$set', {}).items():
                    item[key] = value
                return MagicMock(matched_count=1, modified_count=1)
        return MagicMock(matched_count=0, modified_count=0)

    def delete_one(self, filter):
        for i, item in enumerate(self._items):
            match = True
            for k, v in filter.items():
                if k == '_id':
                    if str(item.get('_id')) != str(v):
                        match = False
                        break
                elif item.get(k) != v:
                    match = False
                    break
            if match:
                self._items.pop(i)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)

    def clear(self):
        self._items.clear()


class MockDatabase:
    """Mock MongoDB database for testing."""

    def __init__(self):
        self._collections = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollection()
        return self._collections[name]


@pytest.fixture
def mock_db():
    """Create mock database and patch get_db."""
    db = MockDatabase()

    def mock_get_db():
        return db

    with patch.object(app_module, 'get_db', mock_get_db):
        yield db
        # Clear all collections after each test
        for collection in db._collections.values():
            collection.clear()


@pytest.fixture
def app():
    """Create application for testing."""
    flask_app.config.update({
        "TESTING": True,
    })
    yield flask_app


@pytest.fixture
def client(app, mock_db):
    """Create test client with mocked database."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create CLI runner."""
    return app.test_cli_runner()

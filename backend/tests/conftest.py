import sys
sys.path.insert(0, '/app/src')

from unittest.mock import MagicMock, patch
import pytest
from bson import ObjectId
import app as app_module
from app import app as flask_app


class MockCursor:
    def __init__(self, items):
        self._items = items
    def __iter__(self):
        return iter(self._items)
    def limit(self, n):
        self._items = self._items[:n]
        return self
    def sort(self, key, direction=1):
        self._items = sorted(self._items, key=lambda x: x.get(key, ''), reverse=(direction == -1))
        return self


class MockCollection:
    def __init__(self):
        self._items = []
    def find(self, filter=None):
        items = list(self._items) if filter is None else [i for i in self._items if all(i.get(k) == v for k, v in filter.items())]
        return MockCursor(items)
    def find_one(self, filter):
        for item in self._items:
            if all(str(item.get(k)) == str(v) if k == '_id' else item.get(k) == v for k, v in filter.items()):
                return item.copy()
        return None
    def insert_one(self, document):
        doc = document.copy()
        doc['_id'] = ObjectId()
        self._items.append(doc)
        return MagicMock(inserted_id=doc['_id'])
    def update_one(self, filter, update):
        for item in self._items:
            if all(str(item.get(k)) == str(v) if k == '_id' else item.get(k) == v for k, v in filter.items()):
                for key, value in update.get('$set', {}).items():
                    item[key] = value
                return MagicMock(matched_count=1, modified_count=1)
        return MagicMock(matched_count=0, modified_count=0)
    def delete_one(self, filter):
        for i, item in enumerate(self._items):
            if all(str(item.get(k)) == str(v) if k == '_id' else item.get(k) == v for k, v in filter.items()):
                self._items.pop(i)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)


class MockDatabase:
    def __init__(self):
        self._collections = {}
    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollection()
        return self._collections[name]


@pytest.fixture
def mock_db():
    db = MockDatabase()
    import auth as auth_module
    def mock_get_db():
        return db
    def mock_decode_token(token):
        return {'user_id': 'test-user-123', 'group_id': 'test-group-456', 'role': 'MANAGER', 'user_name': 'Test User', 'group_name': 'Test Group', 'join_code': 'TEST123'}
    with patch.object(app_module, 'get_db', mock_get_db), patch.object(auth_module, 'decode_token', mock_decode_token):
        yield db
        for collection in db._collections.values():
            collection._items.clear()


@pytest.fixture
def app():
    flask_app.config.update({"TESTING": True})
    yield flask_app


@pytest.fixture
def client(app, mock_db):
    test_client = app.test_client()
    test_client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer test-token'
    return test_client

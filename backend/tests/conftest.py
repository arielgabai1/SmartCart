import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from unittest.mock import MagicMock, patch
import pytest
from bson import ObjectId
import mongomock

# Patch db.get_db BEFORE importing app to prevent real MongoDB connections
import db as db_module
original_get_db = db_module.get_db
db_module.get_db = lambda: None  # Stub out during import

import app as app_module
from app import app as flask_app

# Restore for later use
db_module.get_db = original_get_db

import auth as auth_module

@pytest.fixture(scope='session')
def mock_db_session():
    """Session-scoped database fixture using mongomock."""
    return mongomock.MongoClient().get_database('testdb')

@pytest.fixture
def mock_db(mock_db_session):
    """Function-scoped fixture that clears and patches."""
    db = mock_db_session

    def mock_get_db():
        return db
    def mock_decode_token(token):
        return {'user_id': 'test-user-123', 'group_id': 'test-group-456', 'role': 'MANAGER', 'user_name': 'Test User', 'group_name': 'Test Group', 'join_code': 'TEST123'}

    # Clear all collections before each test
    for collection_name in db.list_collection_names():
        db[collection_name].delete_many({})

    with patch.object(db_module, 'get_db', mock_get_db), patch.object(app_module, 'get_db', mock_get_db), patch.object(auth_module, 'get_db', mock_get_db), patch.object(auth_module, 'decode_token', mock_decode_token):
        yield db


@pytest.fixture(scope='session')
def app():
    """Session-scoped app fixture."""
    flask_app.config.update({"TESTING": True})
    return flask_app


@pytest.fixture
def client(app, mock_db):
    test_client = app.test_client()
    test_client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer test-token'
    return test_client

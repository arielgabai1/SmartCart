import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Set env var for testing before imports run
os.environ['JWT_SECRET'] = 'test-secret-value'

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


# --- Role-based Token Fixtures ---

@pytest.fixture
def as_member(mock_db):
    """Patch token to MEMBER role."""
    def decode(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member User', 'group_name': 'Test Group', 'join_code': 'TEST123'}
    with patch.object(auth_module, 'decode_token', decode):
        yield


@pytest.fixture
def as_other_group(mock_db):
    """Patch token to different group."""
    def decode(token):
        return {'user_id': 'user-b', 'group_id': 'group-B', 'role': 'MANAGER',
                'user_name': 'User B', 'group_name': 'Group B', 'join_code': 'GROUPB'}
    with patch.object(auth_module, 'decode_token', decode):
        yield


# --- Registered Group Fixtures ---

@pytest.fixture
def registered_group(client):
    """Register group, return details."""
    resp = client.post('/api/auth/register', json={
        'group_name': 'Smith Family', 'user_name': 'John Smith',
        'email': 'john@smith.com', 'password': 'secure123'})
    return resp.get_json()['details']


@pytest.fixture
def group_with_member(client, registered_group):
    """Group with admin + member."""
    join = client.post('/api/auth/join', json={
        'join_code': registered_group['join_code'],
        'user_name': 'Jane', 'email': 'jane@smith.com', 'password': 'pass456'})
    return {'admin': registered_group, 'member': join.get_json()['details']}

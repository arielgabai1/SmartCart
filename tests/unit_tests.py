"""
Unit Tests - Business logic and pure functions (no Flask, no database).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
import threading
from bson import ObjectId
from unittest.mock import patch, MagicMock

from models import validate_item, validate_user, validate_group, item_to_dict, user_to_dict, MAX_ITEM_NAME_LENGTH
from auth import hash_password, verify_password, generate_token, decode_token
from ai_engine import estimate_item_price


# --- Item Validation Tests ---

@pytest.mark.unit
def test_validate_item_success():
    """validate_item accepts valid item data with all fields."""
    data = {
        'name': 'Milk', 'group_id': 'test-group-123', 'category': 'Dairy',
        'submitted_by': 'user-456', 'submitted_by_name': 'John Doe',
        'status': 'APPROVED', 'price_nis': 12.5, 'quantity': 2,
        'ai_status': 'COMPLETED', 'ai_latency': 1.23
    }
    validated, errors = validate_item(data)
    assert errors == []
    assert validated['name'] == 'Milk'
    assert validated['status'] == 'APPROVED'
    assert 'created_at' in validated


@pytest.mark.unit
def test_validate_item_minimal_fields():
    """validate_item works with minimal required fields."""
    validated, errors = validate_item({'name': 'Bread', 'group_id': 'group-789'})
    assert errors == []
    assert validated['status'] == 'PENDING'
    assert validated['quantity'] == 1
    assert validated['category'] == 'OTHER'


@pytest.mark.unit
@pytest.mark.parametrize("data,err_substr", [
    ({'group_id': 'g1'}, 'name'),
    ({'name': 'B'}, 'group_id'),
    ({'name': '   ', 'group_id': 'g1'}, 'empty'),
    ({'name': 'x' * (MAX_ITEM_NAME_LENGTH + 1), 'group_id': 'g1'}, 'exceed'),
])
def test_validate_item_required_fields(data, err_substr):
    """validate_item rejects missing or invalid required fields."""
    _, errors = validate_item(data)
    assert any(err_substr in e.lower() for e in errors)


@pytest.mark.unit
def test_validate_item_strips_whitespace():
    """validate_item strips whitespace from name and category."""
    validated, errors = validate_item({'name': '  Eggs  ', 'group_id': 'g1', 'category': '  Protein  '})
    assert errors == []
    assert validated['name'] == 'Eggs'
    assert validated['category'] == 'Protein'


@pytest.mark.unit
@pytest.mark.parametrize("field,value", [
    ('status', 'INVALID'), ('ai_status', 'INVALID'), ('user_role', 'ADMIN'),
    ('quantity', 0), ('quantity', 'abc'), ('price_nis', 'expensive'), ('ai_latency', 'x'),
])
def test_validate_item_invalid_values(field, value):
    """validate_item rejects invalid field values."""
    _, errors = validate_item({'name': 'I', 'group_id': 'g', field: value})
    assert len(errors) > 0


@pytest.mark.unit
def test_validate_item_valid_user_role():
    """validate_item accepts valid user_role."""
    validated, errors = validate_item({'name': 'Item', 'group_id': 'g1', 'user_role': 'MANAGER'})
    assert errors == []
    assert validated['user_role'] == 'MANAGER'


# --- User Validation Tests ---

@pytest.mark.unit
def test_validate_user_success():
    """validate_user accepts valid user data."""
    data = {'email': 'test@example.com', 'password_hash': 'hashed_password_123',
            'group_id': 'group-456', 'role': 'MANAGER', 'full_name': 'John Doe'}
    validated, errors = validate_user(data)
    assert errors == []
    assert validated['email'] == 'test@example.com'
    assert 'created_at' in validated


@pytest.mark.unit
def test_validate_user_email_normalization():
    """validate_user normalizes email to lowercase."""
    validated, errors = validate_user({
        'email': 'Test@Example.COM', 'password_hash': 'hash',
        'group_id': 'group-123', 'role': 'MEMBER'})
    assert errors == []
    assert validated['email'] == 'test@example.com'


@pytest.mark.unit
@pytest.mark.parametrize("email", ['notanemail', '@example.com', 'user@', 'user@.com', ''])
def test_validate_user_invalid_email(email):
    """validate_user rejects invalid email formats."""
    _, errors = validate_user({'email': email, 'password_hash': 'h', 'group_id': 'g', 'role': 'MEMBER'})
    assert any('email' in e.lower() for e in errors)


@pytest.mark.unit
@pytest.mark.parametrize("missing,base", [
    ('email', {'password_hash': 'h', 'group_id': 'g', 'role': 'MEMBER'}),
    ('password_hash', {'email': 't@e.com', 'group_id': 'g', 'role': 'MEMBER'}),
    ('group_id', {'email': 't@e.com', 'password_hash': 'h', 'role': 'MEMBER'}),
    ('role', {'email': 't@e.com', 'password_hash': 'h', 'group_id': 'g'}),
])
def test_validate_user_missing_fields(missing, base):
    """validate_user rejects data missing required fields."""
    _, errors = validate_user(base)
    assert any(missing in e.lower() for e in errors)


@pytest.mark.unit
def test_validate_user_invalid_role():
    """validate_user rejects invalid role values."""
    _, errors = validate_user({'email': 'test@example.com', 'password_hash': 'hash',
                               'group_id': 'group-123', 'role': 'ADMIN'})
    assert any('role' in e.lower() for e in errors)


# --- Group Validation Tests ---

@pytest.mark.unit
def test_validate_group_success():
    """validate_group accepts valid group data."""
    validated, errors = validate_group({'name': 'Smith Family', 'join_code': 'ABC123', 'subscription_tier': 'PREMIUM'})
    assert errors == []
    assert validated['name'] == 'Smith Family'
    assert 'created_at' in validated


@pytest.mark.unit
def test_validate_group_generates_join_code():
    """validate_group generates join_code if not provided."""
    validated, errors = validate_group({'name': 'Johnson Family'})
    assert errors == []
    assert len(validated['join_code']) == 6
    assert validated['subscription_tier'] == 'FREE'


@pytest.mark.unit
@pytest.mark.parametrize("data", [{}, {'name': '   '}])
def test_validate_group_missing_name(data):
    """validate_group rejects missing or empty name."""
    _, errors = validate_group(data)
    assert any('name' in e.lower() for e in errors)


# --- Helper Function Tests ---

@pytest.mark.unit
def test_item_to_dict_converts_objectid():
    """item_to_dict converts MongoDB ObjectId to string."""
    result = item_to_dict({'_id': ObjectId(), 'name': 'Test Item', 'group_id': 'g1', 'status': 'APPROVED'})
    assert isinstance(result['_id'], str)


@pytest.mark.unit
def test_item_to_dict_adds_defaults():
    """item_to_dict adds default values for missing optional fields."""
    result = item_to_dict({'_id': ObjectId(), 'name': 'Test'})
    assert result['ai_status'] is None
    assert result['quantity'] == 1
    assert result['submitted_by_name'] == 'Group Member'


@pytest.mark.unit
def test_item_to_dict_preserves_submitted_by_name():
    """item_to_dict preserves submitted_by_name if present."""
    result = item_to_dict({'_id': ObjectId(), 'name': 'Test', 'submitted_by_name': 'Alice'})
    assert result['submitted_by_name'] == 'Alice'


@pytest.mark.unit
def test_user_to_dict_removes_password():
    """user_to_dict removes password_hash from user data."""
    result = user_to_dict({'_id': ObjectId(), 'email': 't@e.com', 'password_hash': 'secret', 'role': 'MANAGER'})
    assert 'password_hash' not in result
    assert result['email'] == 't@e.com'


# --- Auth Helper Tests ---

@pytest.mark.unit
def test_hash_and_verify_password():
    """hash_password and verify_password work correctly."""
    password = 'my_secure_password'
    hashed = hash_password(password)
    assert hashed.startswith('$2b$')
    assert verify_password(password, hashed) is True
    assert verify_password('wrong', hashed) is False


@pytest.mark.unit
def test_generate_and_decode_token():
    """generate_token creates a valid JWT with all claims."""
    token = generate_token('user-123', 'group-456', 'MANAGER', 'John Doe', 'Smith Family', 'ABC123')
    decoded = decode_token(token)
    assert decoded['user_id'] == 'user-123'
    assert decoded['role'] == 'MANAGER'
    assert 'exp' in decoded


@pytest.mark.unit
@pytest.mark.parametrize("token", ['invalid.token.here', ''])
def test_decode_token_invalid(token):
    """decode_token returns None for invalid token."""
    assert decode_token(token) is None


# --- AI Engine Tests ---

@pytest.mark.unit
def test_ai_engine_fallback_no_api_key(monkeypatch):
    """estimate_item_price returns fallback when OPENAI_API_KEY not set."""
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    price, status = estimate_item_price('Milk', 'Dairy')
    assert price == 0.0 and status == 'ERROR'


@pytest.mark.unit
def test_ai_engine_success(monkeypatch):
    """estimate_item_price returns price and COMPLETED when AI succeeds."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "25.50"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch('ai_engine.get_openai_client', return_value=mock_client):
        monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
        price, status = estimate_item_price('Milk', 'Dairy')

    assert price == 25.5
    assert status == 'COMPLETED'


@pytest.mark.unit
def test_ai_engine_get_client_no_key(monkeypatch):
    """get_openai_client returns None without key."""
    from ai_engine import get_openai_client
    import ai_engine
    ai_engine._client = None
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert get_openai_client() is None


# --- Models Helpers Direct Tests ---

@pytest.mark.unit
def test_models_helpers_direct():
    """Test helper functions in models.py."""
    from models import _validate_required, _validate_string

    errors = []
    _validate_required({}, 'missing', 'Error', errors)
    assert errors == ['Error']

    assert _validate_string("abc", max_len=2) is None
    assert _validate_string("abc", max_len=5) == "abc"
    assert _validate_string(None) is None


# --- Auth Module DB Failure Tests ---

@pytest.mark.unit
def test_auth_module_db_failures():
    """Test auth.py exception handling."""
    from auth import register_group_and_admin, login_user

    mock_db_obj = MagicMock()
    mock_db_obj.__getitem__.return_value.find_one.side_effect = Exception("Auth DB Down")
    mock_db_obj.__getitem__.return_value.insert_one.side_effect = Exception("Auth DB Down")

    with patch('auth.get_db', return_value=mock_db_obj):
        with pytest.raises(Exception, match="Auth DB Down"):
            register_group_and_admin('G', 'U', 'e@e.com', 'p')

        with pytest.raises(Exception, match="Auth DB Down"):
            login_user('e@e.com', 'p')


@pytest.mark.unit
def test_register_group_validation_error():
    """register_group_and_admin returns errors when group validation fails."""
    from auth import register_group_and_admin

    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one.return_value = None

    with patch('auth.get_db', return_value=mock_db):
        result, errors = register_group_and_admin('', 'User', 'e@e.com', 'pass')
        assert result is None
        assert any('name' in e.lower() for e in errors)


@pytest.mark.unit
def test_register_user_validation_error_rollback():
    """register_group_and_admin rolls back group when user validation fails."""
    from auth import register_group_and_admin

    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one.return_value = None
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = ObjectId()
    mock_db.__getitem__.return_value.insert_one.return_value = mock_insert_result

    with patch('auth.get_db', return_value=mock_db), \
         patch('auth.validate_user', return_value=({}, ['Invalid user data'])):
        result, errors = register_group_and_admin('Group', 'User', 'e@e.com', 'pass')
        assert result is None
        assert 'Invalid user data' in errors
        mock_db.__getitem__.return_value.delete_one.assert_called()


@pytest.mark.unit
def test_join_user_validation_error():
    """register_member_via_code returns errors when user validation fails."""
    from auth import register_member_via_code

    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one.side_effect = [
        {'_id': ObjectId(), 'name': 'Group', 'join_code': 'ABC123'},
        None
    ]

    with patch('auth.get_db', return_value=mock_db), \
         patch('auth.validate_user', return_value=({}, ['Invalid user'])):
        result, errors = register_member_via_code('ABC123', 'User', 'e@e.com', 'pass')
        assert result is None
        assert 'Invalid user' in errors


# --- Additional AI Engine Tests ---

@pytest.mark.unit
def test_ai_engine_empty_response(monkeypatch):
    """estimate_item_price handles empty string response."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = ""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch('ai_engine.get_openai_client', return_value=mock_client):
        monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
        price, status = estimate_item_price('Item', 'Cat')

    assert price == 0.0 and status == 'ERROR'


@pytest.mark.unit
def test_ai_engine_whitespace_response(monkeypatch):
    """estimate_item_price handles whitespace-only response."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "   \n  "
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch('ai_engine.get_openai_client', return_value=mock_client):
        monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
        price, status = estimate_item_price('Item', 'Cat')

    assert price == 0.0 and status == 'ERROR'


@pytest.mark.unit
def test_ai_engine_zero_price(monkeypatch):
    """estimate_item_price handles zero price."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "0"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch('ai_engine.get_openai_client', return_value=mock_client):
        monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
        price, status = estimate_item_price('Item', 'Cat')

    assert price == 0.0 and status == 'ERROR'


@pytest.mark.unit
def test_ai_engine_very_large_number(monkeypatch):
    """estimate_item_price handles very large numbers."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "999999.99"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch('ai_engine.get_openai_client', return_value=mock_client):
        monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
        price, status = estimate_item_price('Item', 'Cat')

    assert price == 999999.99 and status == 'COMPLETED'


# --- Additional Validation Tests ---

@pytest.mark.unit
def test_validate_item_boundary_max_name():
    """validate_item accepts max length name."""
    from models import MAX_ITEM_NAME_LENGTH
    long_name = 'x' * MAX_ITEM_NAME_LENGTH
    validated, errors = validate_item({'name': long_name, 'group_id': 'g1'})
    assert errors == []
    assert validated['name'] == long_name


@pytest.mark.unit
def test_validate_item_special_characters():
    """validate_item accepts special characters in name."""
    validated, errors = validate_item({'name': 'Coffee & Tea (2L)', 'group_id': 'g1'})
    assert errors == []
    assert validated['name'] == 'Coffee & Tea (2L)'


@pytest.mark.unit
def test_validate_item_unicode():
    """validate_item accepts unicode characters."""
    validated, errors = validate_item({'name': 'חלב טרי', 'group_id': 'g1'})
    assert errors == []
    assert validated['name'] == 'חלב טרי'


@pytest.mark.unit
def test_validate_user_email_leading_trailing_spaces():
    """validate_user normalizes email with spaces."""
    validated, errors = validate_user({
        'email': '  test@example.com  ',
        'password_hash': 'hash',
        'group_id': 'g',
        'role': 'MEMBER'
    })
    assert errors == []
    assert validated['email'] == 'test@example.com'


@pytest.mark.unit
def test_validate_group_empty_spaces_name():
    """validate_group rejects name with only spaces."""
    _, errors = validate_group({'name': '     '})
    assert any('name' in e.lower() for e in errors)


# --- DB Module Tests ---

@pytest.mark.unit
def test_get_db_connection_ping_failure(monkeypatch):
    """get_db_connection raises error when ping fails."""
    from db import get_db_connection

    mock_client = MagicMock()
    mock_client.admin.command.side_effect = Exception("Ping failed")

    with patch('db.MongoClient', return_value=mock_client):
        monkeypatch.setattr('time.sleep', lambda x: None)
        with pytest.raises(Exception):
            get_db_connection(max_retries=1)


@pytest.mark.unit
def test_get_db_uses_env_uri(monkeypatch):
    """get_db_connection uses MONGO_URI from environment."""
    from db import get_db_connection

    custom_uri = 'mongodb://custom:27017/testdb'
    monkeypatch.setenv('MONGO_URI', custom_uri)

    mock_client = MagicMock()

    with patch('db.MongoClient', return_value=mock_client) as mock_mongo:
        get_db_connection(max_retries=1)
        mock_mongo.assert_called_once()
        call_args = mock_mongo.call_args[0][0]
        assert call_args == custom_uri


# --- Token Edge Cases ---

@pytest.mark.unit
def test_generate_token_with_special_chars():
    """generate_token handles special characters in fields."""
    token = generate_token('user-123', 'group-456', 'MANAGER', "John O'Brien", 'Smith & Co', 'ABC123')
    decoded = decode_token(token)
    assert decoded['user_name'] == "John O'Brien"
    assert decoded['group_name'] == 'Smith & Co'


@pytest.mark.unit
def test_decode_token_expired():
    """decode_token returns None for expired token."""
    import jwt
    import os
    from datetime import datetime, timedelta, timezone

    secret = os.getenv('JWT_SECRET', 'test-secret-value')
    expired_token = jwt.encode(
        {'user_id': 'test', 'exp': datetime.now(timezone.utc) - timedelta(hours=1)},
        secret,
        algorithm='HS256'
    )

    assert decode_token(expired_token) is None


@pytest.mark.unit
def test_decode_token_malformed():
    """decode_token returns None for malformed token."""
    assert decode_token('not.a.valid.jwt.token.at.all') is None


# --- Metrics Server Tests ---

@pytest.mark.unit
def test_metrics_server_starts_thread():
    """run_metrics_server starts a daemon thread for periodic updates."""
    from metrics_server import run_metrics_server
    import threading

    captured = {}

    def mock_run_simple(*args, **kwargs):
        captured['port'] = args[1]
        captured['threaded'] = kwargs.get('threaded')

    update_calls = []

    def mock_update():
        update_calls.append(1)

    with patch('metrics_server.run_simple', mock_run_simple), \
         patch('metrics_server.threading.Thread') as mock_thread:
        mock_thread.return_value = MagicMock()
        run_metrics_server(mock_update)

        mock_thread.assert_called_once()
        assert mock_thread.call_args[1]['daemon'] is True


@pytest.mark.unit
def test_metrics_server_uses_env_port(monkeypatch):
    """run_metrics_server reads METRICS_PORT from environment."""
    from metrics_server import run_metrics_server

    captured = {}

    def mock_run_simple(*args, **kwargs):
        captured['port'] = args[1]

    monkeypatch.setenv('METRICS_PORT', '9123')

    with patch('metrics_server.run_simple', mock_run_simple), \
         patch('metrics_server.threading.Thread', MagicMock()):
        run_metrics_server(lambda: None)

    assert captured['port'] == 9123


@pytest.mark.unit
def test_metrics_server_default_port(monkeypatch):
    """run_metrics_server defaults to port 8081."""
    from metrics_server import run_metrics_server

    captured = {}

    def mock_run_simple(*args, **kwargs):
        captured['port'] = args[1]

    monkeypatch.delenv('METRICS_PORT', raising=False)

    with patch('metrics_server.run_simple', mock_run_simple), \
         patch('metrics_server.threading.Thread', MagicMock()):
        run_metrics_server(lambda: None)

    assert captured['port'] == 8081


@pytest.mark.unit
def test_metrics_server_dispatcher_middleware():
    """run_metrics_server creates DispatcherMiddleware with /metrics path."""
    from metrics_server import run_metrics_server

    captured_app = {}

    def mock_run_simple(host, port, app, **kwargs):
        captured_app['app'] = app

    with patch('metrics_server.run_simple', mock_run_simple), \
         patch('metrics_server.threading.Thread', MagicMock()):
        run_metrics_server(lambda: None)

    assert captured_app['app'] is not None


# --- Metrics Utils Tests ---

@pytest.mark.unit
def test_update_db_metrics_success():
    """update_db_metrics sets gauges when database is available."""
    from metrics_utils import update_db_metrics

    mock_gauge_connections = MagicMock()
    mock_gauge_items = MagicMock()

    mock_db = MagicMock()
    mock_db.__getitem__.return_value.count_documents.return_value = 42

    mock_client = MagicMock()
    mock_client.admin.command.return_value = {'connections': {'current': 5}}

    with patch('metrics_utils.db.get_db', return_value=mock_db), \
         patch('metrics_utils.db.db_client', mock_client):
        update_db_metrics(mock_gauge_connections, mock_gauge_items)

    mock_gauge_items.set.assert_called_once_with(42)
    mock_gauge_connections.set.assert_called_once_with(5)


@pytest.mark.unit
def test_update_db_metrics_db_none():
    """update_db_metrics handles None database gracefully."""
    from metrics_utils import update_db_metrics

    mock_gauge_connections = MagicMock()
    mock_gauge_items = MagicMock()

    with patch('metrics_utils.db.get_db', return_value=None):
        update_db_metrics(mock_gauge_connections, mock_gauge_items)

    mock_gauge_items.set.assert_not_called()
    mock_gauge_connections.set.assert_not_called()


@pytest.mark.unit
def test_update_db_metrics_server_status_fallback():
    """update_db_metrics falls back to 1 when serverStatus fails."""
    from metrics_utils import update_db_metrics

    mock_gauge_connections = MagicMock()
    mock_gauge_items = MagicMock()

    mock_db = MagicMock()
    mock_db.__getitem__.return_value.count_documents.return_value = 10

    mock_client = MagicMock()
    mock_client.admin.command.side_effect = Exception("Permission denied")

    with patch('metrics_utils.db.get_db', return_value=mock_db), \
         patch('metrics_utils.db.db_client', mock_client):
        update_db_metrics(mock_gauge_connections, mock_gauge_items)

    mock_gauge_items.set.assert_called_once_with(10)
    mock_gauge_connections.set.assert_called_once_with(1)


@pytest.mark.unit
def test_update_db_metrics_exception_logged(caplog):
    """update_db_metrics logs errors on exception."""
    from metrics_utils import update_db_metrics
    import logging

    mock_gauge = MagicMock()

    with patch('metrics_utils.db.get_db', side_effect=Exception("DB error")):
        with caplog.at_level(logging.ERROR):
            update_db_metrics(mock_gauge, mock_gauge)

    assert any('Error updating DB metrics' in r.message for r in caplog.records)


# --- Middleware Tests ---

@pytest.mark.unit
def test_before_request_sets_trace_id():
    """before_request sets g.trace_id from header or generates one."""
    from app import app

    with app.test_client() as client:
        response = client.get('/api/health', headers={'X-Trace-ID': 'custom-trace'})
        assert response.status_code == 200


@pytest.mark.unit
def test_after_request_skips_health_metrics():
    """after_request skips logging for /api/health endpoint."""
    from app import app

    with patch('app.REQUEST_COUNT') as mock_counter:
        with app.test_client() as client:
            client.get('/api/health')
        mock_counter.labels.assert_not_called()


@pytest.mark.unit
def test_after_request_logs_500_as_error(caplog):
    """after_request logs 500 errors at ERROR level."""
    from app import app
    import logging

    with patch('auth.get_db', side_effect=Exception("DB down")):
        with app.test_client() as client:
            with caplog.at_level(logging.ERROR):
                client.post('/api/auth/register', json={
                    'group_name': 'G', 'user_name': 'U',
                    'email': 'e@e.com', 'password': 'p'
                })


@pytest.mark.unit
def test_after_request_handles_exception():
    """after_request catches its own errors without crashing."""
    from app import app

    with patch('app.REQUEST_COUNT.labels', side_effect=Exception("Metrics error")):
        with app.test_client() as client:
            response = client.get('/api/auth/me')
            assert response.status_code in [200, 401]


@pytest.mark.unit
def test_after_request_increments_request_count():
    """after_request increments REQUEST_COUNT for non-health endpoints."""
    from app import app

    with patch('app.REQUEST_COUNT') as mock_counter, \
         patch('app.REQUEST_LATENCY') as mock_histogram, \
         patch('app.login_user', return_value=(None, ['fail'])):
        mock_counter.labels.return_value = MagicMock()
        mock_histogram.labels.return_value = MagicMock()

        with app.test_client() as client:
            client.post('/api/auth/login', json={'email': 'e@e.com', 'password': 'p'})

        mock_counter.labels.assert_called()


# --- Error Response Helper Tests ---

@pytest.mark.unit
def test_error_response_basic():
    """error_response returns correct structure without details."""
    from app import app, error_response

    with app.app_context():
        response, code = error_response('Something went wrong', 400)
        data = response.get_json()

        assert code == 400
        assert data['error'] == 'Something went wrong'
        assert 'details' not in data


@pytest.mark.unit
def test_error_response_with_details():
    """error_response includes details when provided."""
    from app import app, error_response

    with app.app_context():
        response, code = error_response('Validation failed', 422, ['Field X is required'])
        data = response.get_json()

        assert code == 422
        assert data['error'] == 'Validation failed'
        assert data['details'] == ['Field X is required']


@pytest.mark.unit
def test_error_response_default_code():
    """error_response defaults to 400 status code."""
    from app import app, error_response

    with app.app_context():
        _, code = error_response('Bad request')
        assert code == 400


# --- Auth Decorator Edge Cases ---

@pytest.mark.unit
def test_auth_required_missing_header():
    """auth_required returns 401 when Authorization header is missing."""
    from app import app

    with app.test_client() as client:
        response = client.get('/api/auth/me')
        assert response.status_code == 401
        assert 'Token is missing' in response.get_json()['details']


@pytest.mark.unit
def test_auth_required_missing_bearer_prefix():
    """auth_required returns 401 when Bearer prefix is missing."""
    from app import app

    with app.test_client() as client:
        response = client.get('/api/auth/me', headers={'Authorization': 'just-a-token'})
        assert response.status_code == 401


@pytest.mark.unit
def test_auth_required_invalid_token():
    """auth_required returns 401 for invalid token."""
    from app import app

    with app.test_client() as client:
        response = client.get('/api/auth/me', headers={'Authorization': 'Bearer invalid.token.here'})
        assert response.status_code == 401
        assert 'invalid or expired' in response.get_json()['details']


@pytest.mark.unit
def test_auth_required_db_fallback():
    """auth_required falls back to token claims when DB unavailable."""
    from app import app
    from auth import generate_token

    token = generate_token('user-123', 'group-456', 'MEMBER', 'Token User', 'Test Group', 'ABC123')

    with patch('auth.get_db', side_effect=Exception("DB unavailable")):
        with app.test_client() as client:
            response = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
            assert response.status_code == 200
            data = response.get_json()
            assert data['role'] == 'MEMBER'


# --- Threading Tests ---

@pytest.mark.unit
def test_create_item_spawns_ai_thread():
    """create_item spawns a daemon thread for AI estimation."""
    from app import app
    from auth import generate_token

    token = generate_token('user-123', 'group-456', 'MANAGER', 'Test User', 'Test Group', 'ABC123')

    threads_created = []
    original_thread = threading.Thread

    def track_thread(*args, **kwargs):
        threads_created.append(kwargs)
        mock = MagicMock()
        return mock

    mock_db = MagicMock()
    mock_db.__getitem__.return_value.insert_one.return_value = MagicMock(inserted_id=ObjectId())
    mock_db.__getitem__.return_value.find_one.return_value = None

    with patch('app.threading.Thread', side_effect=track_thread), \
         patch('app.get_db', return_value=mock_db), \
         patch('auth.get_db', return_value=mock_db):
        with app.test_client() as client:
            response = client.post('/api/items',
                                   json={'name': 'Test Item', 'category': 'Test'},
                                   headers={'Authorization': f'Bearer {token}'})
            assert response.status_code == 201

    assert any(t.get('daemon') is True for t in threads_created)


# --- Health Endpoint Tests ---

@pytest.mark.unit
def test_health_endpoint_db_down():
    """Health endpoint returns 503 when DB is down."""
    from app import app

    mock_client = MagicMock()
    mock_client.admin.command.side_effect = Exception("Connection refused")

    with patch('app.db.db_client', mock_client):
        with app.test_client() as client:
            response = client.get('/api/health')
            assert response.status_code == 503
            assert response.get_json()['status'] == 'unhealthy'


@pytest.mark.unit
def test_health_endpoint_db_up():
    """Health endpoint returns 200 when DB is healthy."""
    from app import app

    mock_client = MagicMock()
    mock_client.admin.command.return_value = {'ok': 1}

    with patch('app.db.db_client', mock_client):
        with app.test_client() as client:
            response = client.get('/api/health')
            assert response.status_code == 200
            assert response.get_json()['status'] == 'healthy'


# --- Invalid ObjectId Tests ---

@pytest.mark.unit
def test_invalid_objectid_in_url():
    """Invalid ObjectId in URL returns 400."""
    from app import app
    from auth import generate_token

    token = generate_token('user-123', 'group-456', 'MANAGER', 'Test', 'Group', 'ABC')

    with patch('auth.get_db', side_effect=Exception("skip")):
        with app.test_client() as client:
            response = client.put('/api/items/not-a-valid-id',
                                  json={'quantity': 5},
                                  headers={'Authorization': f'Bearer {token}'})
            assert response.status_code == 400
            assert 'Invalid item ID' in response.get_json()['error']


@pytest.mark.unit
def test_invalid_objectid_in_delete():
    """Invalid ObjectId in DELETE returns 400."""
    from app import app
    from auth import generate_token

    token = generate_token('user-123', 'group-456', 'MANAGER', 'Test', 'Group', 'ABC')

    with patch('auth.get_db', side_effect=Exception("skip")):
        with app.test_client() as client:
            response = client.delete('/api/items/bad-id',
                                     headers={'Authorization': f'Bearer {token}'})
            assert response.status_code == 400


# --- JSON Handling Tests ---

@pytest.mark.unit
def test_malformed_json_returns_400():
    """Malformed JSON body returns 400."""
    from app import app
    from auth import generate_token

    token = generate_token('user-123', 'group-456', 'MANAGER', 'Test', 'Group', 'ABC')

    with patch('auth.get_db', side_effect=Exception("skip")):
        with app.test_client() as client:
            response = client.post('/api/items',
                                   data='not json',
                                   content_type='application/json',
                                   headers={'Authorization': f'Bearer {token}'})
            assert response.status_code == 400


@pytest.mark.unit
def test_missing_json_body_returns_400():
    """Missing JSON body returns 400."""
    from app import app
    from auth import generate_token

    token = generate_token('user-123', 'group-456', 'MANAGER', 'Test', 'Group', 'ABC')

    with patch('auth.get_db', side_effect=Exception("skip")):
        with app.test_client() as client:
            response = client.post('/api/items',
                                   content_type='application/json',
                                   headers={'Authorization': f'Bearer {token}'})
            assert response.status_code == 400


# --- Token Edge Cases ---

@pytest.mark.unit
def test_generate_token_with_none_join_code():
    """generate_token handles None join_code."""
    token = generate_token('user-123', 'group-456', 'MEMBER', 'Test User', 'Test Group', None)
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded['join_code'] is None


@pytest.mark.unit
def test_validate_item_large_quantity():
    """validate_item handles large quantity values."""
    validated, errors = validate_item({'name': 'Bulk Item', 'group_id': 'g1', 'quantity': 9999})
    assert errors == []
    assert validated['quantity'] == 9999


# --- Route Handler Tests ---

def _auth_headers(role='MANAGER'):
    """Generate auth headers with a valid token for protected route tests."""
    token = generate_token(
        '507f1f77bcf86cd799439011', 'group-456', role,
        'Test User', 'Test Group', 'ABC123'
    )
    return {'Authorization': f'Bearer {token}'}


# Auth Routes

@pytest.mark.unit
def test_register_route_success():
    """Register endpoint returns 201 on success."""
    from app import app
    auth_data = {'user_id': 'u1', 'group_id': 'g1', 'role': 'MANAGER',
                 'join_code': 'XYZ', 'token': 'tok'}
    with patch('app.register_group_and_admin', return_value=(auth_data, [])):
        with app.test_client() as c:
            r = c.post('/api/auth/register', json={
                'group_name': 'G', 'user_name': 'U',
                'email': 'e@e.com', 'password': 'p'
            })
            assert r.status_code == 201
            assert r.get_json()['details']['join_code'] == 'XYZ'


@pytest.mark.unit
def test_register_route_missing_fields():
    """Register endpoint returns 400 when fields are missing."""
    from app import app
    with app.test_client() as c:
        r = c.post('/api/auth/register', json={'group_name': 'G'})
        assert r.status_code == 400


@pytest.mark.unit
def test_register_route_errors():
    """Register endpoint returns 400 on validation errors."""
    from app import app
    with patch('app.register_group_and_admin', return_value=(None, ['exists'])):
        with app.test_client() as c:
            r = c.post('/api/auth/register', json={
                'group_name': 'G', 'user_name': 'U',
                'email': 'e@e.com', 'password': 'p'
            })
            assert r.status_code == 400


@pytest.mark.unit
def test_join_route_success():
    """Join endpoint returns 201 on success."""
    from app import app
    auth_data = {'user_id': 'u1', 'group_id': 'g1', 'role': 'MEMBER', 'token': 'tok'}
    with patch('app.register_member_via_code', return_value=(auth_data, [])):
        with app.test_client() as c:
            r = c.post('/api/auth/join', json={
                'join_code': 'ABC', 'user_name': 'U',
                'email': 'e@e.com', 'password': 'p'
            })
            assert r.status_code == 201


@pytest.mark.unit
def test_join_route_missing_fields():
    """Join endpoint returns 400 when fields are missing."""
    from app import app
    with app.test_client() as c:
        r = c.post('/api/auth/join', json={'join_code': 'ABC'})
        assert r.status_code == 400


@pytest.mark.unit
def test_join_route_errors():
    """Join endpoint returns 400 on validation errors."""
    from app import app
    with patch('app.register_member_via_code', return_value=(None, ['bad code'])):
        with app.test_client() as c:
            r = c.post('/api/auth/join', json={
                'join_code': 'BAD', 'user_name': 'U',
                'email': 'e@e.com', 'password': 'p'
            })
            assert r.status_code == 400


@pytest.mark.unit
def test_login_route_success():
    """Login endpoint returns 200 with token."""
    from app import app
    with patch('app.login_user', return_value=('token123', [])):
        with app.test_client() as c:
            r = c.post('/api/auth/login', json={
                'email': 'e@e.com', 'password': 'p'
            })
            assert r.status_code == 200
            assert r.get_json()['token'] == 'token123'


@pytest.mark.unit
def test_login_route_missing_fields():
    """Login endpoint returns 400 when credentials missing."""
    from app import app
    with app.test_client() as c:
        r = c.post('/api/auth/login', json={'email': 'e@e.com'})
        assert r.status_code == 400


@pytest.mark.unit
def test_login_route_failure():
    """Login endpoint returns 401 on bad credentials."""
    from app import app
    with patch('app.login_user', return_value=(None, ['Bad creds'])):
        with app.test_client() as c:
            r = c.post('/api/auth/login', json={
                'email': 'e@e.com', 'password': 'wrong'
            })
            assert r.status_code == 401


# Item Routes

@pytest.mark.unit
def test_get_items_success():
    """GET /api/items returns items for the group."""
    from app import app
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find.return_value.sort.return_value.limit.return_value = [
        {'_id': ObjectId(), 'name': 'Milk', 'group_id': 'g', 'status': 'APPROVED'}
    ]
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.get('/api/items', headers=_auth_headers())
            assert r.status_code == 200
            assert len(r.get_json()) == 1


@pytest.mark.unit
def test_get_items_db_error():
    """GET /api/items returns 500 on DB error."""
    from app import app
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', side_effect=Exception("DB down")):
        with app.test_client() as c:
            r = c.get('/api/items', headers=_auth_headers())
            assert r.status_code == 500


@pytest.mark.unit
def test_update_item_status_manager():
    """Manager can approve an item."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'status': 'PENDING', 'submitted_by': 'other-user'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/items/{item_id}',
                      json={'status': 'APPROVED'},
                      headers=_auth_headers('MANAGER'))
            assert r.status_code == 200


@pytest.mark.unit
def test_update_item_not_found():
    """PUT /api/items/<id> returns 404 when item not in group."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = None
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/items/{item_id}',
                      json={'status': 'APPROVED'},
                      headers=_auth_headers())
            assert r.status_code == 404


@pytest.mark.unit
def test_update_item_status_non_manager():
    """Member cannot approve items."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'status': 'PENDING', 'submitted_by': 'other'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/items/{item_id}',
                      json={'status': 'APPROVED'},
                      headers=_auth_headers('MEMBER'))
            assert r.status_code == 403


@pytest.mark.unit
def test_update_item_quantity_member_own_pending():
    """Member can update quantity on their own pending item."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'status': 'PENDING', 'submitted_by': '507f1f77bcf86cd799439011'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/items/{item_id}',
                      json={'quantity': 3},
                      headers=_auth_headers('MEMBER'))
            assert r.status_code == 200


@pytest.mark.unit
def test_update_item_quantity_member_not_owner():
    """Member cannot update quantity on another user's item."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'status': 'PENDING', 'submitted_by': 'other-user'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/items/{item_id}',
                      json={'quantity': 3},
                      headers=_auth_headers('MEMBER'))
            assert r.status_code == 403


@pytest.mark.unit
def test_update_item_invalid_quantity_zero():
    """Quantity less than 1 returns 400."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'status': 'PENDING', 'submitted_by': 'other'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/items/{item_id}',
                      json={'quantity': 0},
                      headers=_auth_headers())
            assert r.status_code == 400


@pytest.mark.unit
def test_update_item_invalid_quantity_string():
    """Non-numeric quantity returns 400."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'status': 'PENDING', 'submitted_by': 'other'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/items/{item_id}',
                      json={'quantity': 'abc'},
                      headers=_auth_headers())
            assert r.status_code == 400


@pytest.mark.unit
def test_update_item_no_fields():
    """Empty update body returns 400."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'status': 'PENDING', 'submitted_by': 'other'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/items/{item_id}',
                      json={},
                      headers=_auth_headers())
            assert r.status_code == 400


@pytest.mark.unit
def test_update_item_reject_sets_author():
    """Rejecting an item sets rejected_by fields."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'status': 'PENDING', 'submitted_by': 'other'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/items/{item_id}',
                      json={'status': 'REJECTED'},
                      headers=_auth_headers('MANAGER'))
            assert r.status_code == 200
            update_fields = col.update_one.call_args[0][1]['$set']
            assert 'rejected_by' in update_fields


# Delete Item

@pytest.mark.unit
def test_delete_item_manager():
    """Manager can delete any item."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456', 'submitted_by': 'other-user'
    }
    col.delete_one.return_value = MagicMock(deleted_count=1)
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.delete(f'/api/items/{item_id}', headers=_auth_headers('MANAGER'))
            assert r.status_code == 204


@pytest.mark.unit
def test_delete_item_owner():
    """Owner can delete their own item."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'submitted_by': '507f1f77bcf86cd799439011'
    }
    col.delete_one.return_value = MagicMock(deleted_count=1)
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.delete(f'/api/items/{item_id}', headers=_auth_headers('MEMBER'))
            assert r.status_code == 204


@pytest.mark.unit
def test_delete_item_not_found():
    """DELETE returns 404 when item not in group."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = None
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.delete(f'/api/items/{item_id}', headers=_auth_headers())
            assert r.status_code == 404


@pytest.mark.unit
def test_delete_item_not_owner():
    """Member cannot delete another user's item."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456', 'submitted_by': 'other-user'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.delete(f'/api/items/{item_id}', headers=_auth_headers('MEMBER'))
            assert r.status_code == 403


@pytest.mark.unit
def test_delete_item_already_deleted():
    """DELETE returns 404 when item was deleted between find and delete."""
    from app import app
    item_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': item_id, 'group_id': 'group-456',
        'submitted_by': '507f1f77bcf86cd799439011'
    }
    col.delete_one.return_value = MagicMock(deleted_count=0)
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.delete(f'/api/items/{item_id}', headers=_auth_headers())
            assert r.status_code == 404


# Delete All Items

@pytest.mark.unit
def test_delete_all_items_manager():
    """Manager can clear all items."""
    from app import app
    mock_db = MagicMock()
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.delete('/api/items/clear', headers=_auth_headers('MANAGER'))
            assert r.status_code == 204


@pytest.mark.unit
def test_delete_all_items_non_manager():
    """Member cannot clear items."""
    from app import app
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=MagicMock()):
        with app.test_client() as c:
            r = c.delete('/api/items/clear', headers=_auth_headers('MEMBER'))
            assert r.status_code == 403


# Group Member Routes

@pytest.mark.unit
def test_get_group_members_success():
    """GET /api/groups/members returns member list."""
    from app import app
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find.return_value = [
        {'_id': ObjectId(), 'full_name': 'Alice', 'email': 'a@a.com', 'role': 'MANAGER'},
        {'_id': ObjectId(), 'full_name': 'Bob', 'email': 'b@b.com', 'role': 'MEMBER'},
    ]
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.get('/api/groups/members', headers=_auth_headers())
            assert r.status_code == 200
            assert len(r.get_json()) == 2


@pytest.mark.unit
def test_manage_member_promote():
    """Manager can promote a member."""
    from app import app
    target_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': target_id, 'group_id': 'group-456',
        'role': 'MEMBER', 'full_name': 'Bob'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/groups/members/{target_id}',
                      json={'role': 'MANAGER'},
                      headers=_auth_headers('MANAGER'))
            assert r.status_code == 200


@pytest.mark.unit
def test_manage_member_remove():
    """Manager can remove a member."""
    from app import app
    target_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': target_id, 'group_id': 'group-456',
        'role': 'MEMBER', 'full_name': 'Bob'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.delete(f'/api/groups/members/{target_id}',
                         headers=_auth_headers('MANAGER'))
            assert r.status_code == 204


@pytest.mark.unit
def test_manage_member_non_manager():
    """Member cannot manage other members."""
    from app import app
    target_id = ObjectId()
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=MagicMock()):
        with app.test_client() as c:
            r = c.put(f'/api/groups/members/{target_id}',
                      json={'role': 'MANAGER'},
                      headers=_auth_headers('MEMBER'))
            assert r.status_code == 403


@pytest.mark.unit
def test_manage_member_self():
    """Manager cannot promote/remove themselves."""
    from app import app
    self_id = ObjectId('507f1f77bcf86cd799439011')
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': self_id, 'group_id': 'group-456',
        'role': 'MANAGER', 'full_name': 'Test User'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/groups/members/{self_id}',
                      json={'role': 'MEMBER'},
                      headers=_auth_headers('MANAGER'))
            assert r.status_code == 400


@pytest.mark.unit
def test_manage_member_invalid_id():
    """Invalid user ID returns 400."""
    from app import app
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=MagicMock()):
        with app.test_client() as c:
            r = c.put('/api/groups/members/bad-id',
                      json={'role': 'MANAGER'},
                      headers=_auth_headers('MANAGER'))
            assert r.status_code == 400


@pytest.mark.unit
def test_manage_member_not_found():
    """Returns 404 when target user not in group."""
    from app import app
    target_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = None
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/groups/members/{target_id}',
                      json={'role': 'MANAGER'},
                      headers=_auth_headers('MANAGER'))
            assert r.status_code == 404


@pytest.mark.unit
def test_manage_member_invalid_role():
    """Invalid role value returns 400."""
    from app import app
    target_id = ObjectId()
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = {
        '_id': target_id, 'group_id': 'group-456',
        'role': 'MEMBER', 'full_name': 'Bob'
    }
    with patch('auth.get_db', side_effect=Exception("skip")), \
         patch('app.get_db', return_value=mock_db):
        with app.test_client() as c:
            r = c.put(f'/api/groups/members/{target_id}',
                      json={'role': 'ADMIN'},
                      headers=_auth_headers('MANAGER'))
            assert r.status_code == 400

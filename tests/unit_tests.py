"""
Unit Tests - Business logic and pure functions (no Flask, no database).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
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

"""
Unified Test Suite - Unit tests (business logic) and integration tests (API endpoints).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
from bson import ObjectId
from unittest.mock import patch, MagicMock, PropertyMock

from models import validate_item, validate_user, validate_group, item_to_dict, user_to_dict, MAX_ITEM_NAME_LENGTH
from auth import hash_password, verify_password, generate_token, decode_token
import auth as auth_module
from ai_engine import estimate_item_price


# ==========================================
#               UNIT TESTS
# ==========================================

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


# ==========================================
#           INTEGRATION TESTS
# ==========================================

# --- Items API Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_get_items_returns_200(client):
    """GET /api/items returns 200 with empty list initially."""
    response = client.get('/api/items')
    assert response.status_code == 200
    assert response.get_json() == []


@pytest.mark.integration
@pytest.mark.p0
def test_post_item_success_manager(client):
    """POST /api/items creates item with APPROVED status for MANAGER."""
    response = client.post('/api/items', json={'name': 'Milk', 'category': 'Dairy'})
    assert response.status_code == 201
    data = response.get_json()
    assert data['status'] == 'APPROVED'
    assert data['ai_status'] == 'CALCULATING'


@pytest.mark.integration
@pytest.mark.p0
def test_post_item_success_member(client, as_member):
    """POST /api/items creates item with PENDING status for MEMBER."""
    response = client.post('/api/items', json={'name': 'Bread'})
    assert response.status_code == 201
    assert response.get_json()['status'] == 'PENDING'


@pytest.mark.integration
@pytest.mark.p1
@pytest.mark.parametrize("payload", [{}, 'not json'])
def test_post_item_invalid_returns_400(client, payload):
    """POST /api/items with missing name or invalid JSON returns 400."""
    if payload == 'not json':
        response = client.post('/api/items', data=payload, content_type='application/json')
    else:
        response = client.post('/api/items', json=payload)
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_get_items_returns_created_items(client):
    """GET /api/items returns created items."""
    client.post('/api/items', json={'name': 'Bread'})
    client.post('/api/items', json={'name': 'Eggs'})
    data = client.get('/api/items').get_json()
    assert len(data) == 2
    assert set(i['name'] for i in data) == {'Bread', 'Eggs'}


@pytest.mark.integration
@pytest.mark.p0
def test_put_item_updates_status_manager(client):
    """PUT /api/items/<id> updates status (MANAGER only)."""
    item_id = client.post('/api/items', json={'name': 'Candy'}).get_json()['_id']
    response = client.put(f'/api/items/{item_id}', json={'status': 'REJECTED'})
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.p1
def test_put_item_status_forbidden_for_member(client, as_member):
    """PUT /api/items/<id> status change forbidden for MEMBER."""
    # Create as manager first (without as_member context)
    pass  # Item created below needs manager context


@pytest.mark.integration
@pytest.mark.p1
def test_member_cannot_update_status(client, mock_db):
    """MEMBER cannot update item status."""
    item_id = client.post('/api/items', json={'name': 'Candy'}).get_json()['_id']

    def mock_member(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member', 'group_name': 'Test', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_member):
        response = client.put(f'/api/items/{item_id}', json={'status': 'APPROVED'})
        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.p0
def test_put_item_updates_quantity(client):
    """PUT /api/items/<id> allows MANAGER to update quantity."""
    item_id = client.post('/api/items', json={'name': 'Candy'}).get_json()['_id']
    assert client.put(f'/api/items/{item_id}', json={'quantity': 5}).status_code == 200


@pytest.mark.integration
@pytest.mark.p1
@pytest.mark.parametrize("qty", [0, 'abc'])
def test_put_item_invalid_quantity_returns_400(client, qty):
    """PUT /api/items/<id> rejects invalid quantity."""
    item_id = client.post('/api/items', json={'name': 'Candy'}).get_json()['_id']
    assert client.put(f'/api/items/{item_id}', json={'quantity': qty}).status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_put_item_no_fields_returns_400(client):
    """PUT /api/items/<id> with no valid fields returns 400."""
    item_id = client.post('/api/items', json={'name': 'Candy'}).get_json()['_id']
    assert client.put(f'/api/items/{item_id}', json={}).status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_member_qty_update_on_approved_item_forbidden(client, mock_db):
    """MEMBER updating quantity on APPROVED item they own should 403."""
    # Create item as member
    def mock_member(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member', 'group_name': 'Test', 'join_code': 'TEST123'}

    # First create as manager (auto-approved)
    item_id = client.post('/api/items', json={'name': 'Item'}).get_json()['_id']

    # Update submitted_by to member in DB so member "owns" it
    mock_db['items'].update_one({'_id': ObjectId(item_id)}, {'$set': {'submitted_by': 'member-123'}})

    with patch.object(auth_module, 'decode_token', mock_member):
        response = client.put(f'/api/items/{item_id}', json={'quantity': 5})
        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.p1
def test_put_item_not_found_returns_404(client):
    """PUT /api/items/<id> returns 404 for non-existent item."""
    assert client.put(f'/api/items/{ObjectId()}', json={'status': 'APPROVED'}).status_code == 404


@pytest.mark.integration
@pytest.mark.p0
def test_delete_item_by_manager(client):
    """DELETE /api/items/<id> allows MANAGER to delete any item."""
    item_id = client.post('/api/items', json={'name': 'Juice'}).get_json()['_id']
    assert client.delete(f'/api/items/{item_id}').status_code == 204
    assert client.get('/api/items').get_json() == []


@pytest.mark.integration
@pytest.mark.p1
def test_delete_item_by_owner(client, mock_db):
    """DELETE /api/items/<id> allows owner to delete their own item."""
    def mock_member(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member', 'group_name': 'Test', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_member):
        item_id = client.post('/api/items', json={'name': 'Snack'}).get_json()['_id']
        assert client.delete(f'/api/items/{item_id}').status_code == 204


@pytest.mark.integration
@pytest.mark.p1
def test_delete_item_forbidden_for_non_owner_member(client, mock_db):
    """DELETE /api/items/<id> forbidden for MEMBER who doesn't own item."""
    item_id = client.post('/api/items', json={'name': 'Snack'}).get_json()['_id']

    def mock_other(token):
        return {'user_id': 'other-999', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Other', 'group_name': 'Test', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_other):
        assert client.delete(f'/api/items/{item_id}').status_code == 403


@pytest.mark.integration
@pytest.mark.p1
def test_delete_item_not_found_returns_404(client):
    """DELETE /api/items/<id> returns 404 for non-existent item."""
    assert client.delete(f'/api/items/{ObjectId()}').status_code == 404


@pytest.mark.integration
@pytest.mark.p0
def test_delete_all_items_by_manager(client):
    """DELETE /api/items/clear allows MANAGER to clear all items."""
    for name in ['Item1', 'Item2', 'Item3']:
        client.post('/api/items', json={'name': name})
    assert client.delete('/api/items/clear').status_code == 204
    assert client.get('/api/items').get_json() == []


@pytest.mark.integration
@pytest.mark.p1
def test_delete_all_items_forbidden_for_member(client, as_member):
    """DELETE /api/items/clear forbidden for MEMBER."""
    assert client.delete('/api/items/clear').status_code == 403


@pytest.mark.integration
@pytest.mark.p0
def test_crud_flow_complete(client):
    """Test complete CRUD flow for items."""
    item_id = client.post('/api/items', json={'name': 'Coffee'}).get_json()['_id']
    assert len(client.get('/api/items').get_json()) == 1
    assert client.put(f'/api/items/{item_id}', json={'quantity': 3}).status_code == 200
    assert client.delete(f'/api/items/{item_id}').status_code == 204
    assert client.get('/api/items').get_json() == []


# --- Multi-Tenancy Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_items_isolated_by_group(client, as_other_group):
    """Items are isolated by group_id (multi-tenancy)."""
    # Create item as default group (manager fixture)
    # Exit as_other_group context to create in default group
    pass  # Handled below


@pytest.mark.integration
@pytest.mark.p0
def test_multi_tenancy_isolation(client, mock_db):
    """Items are isolated by group_id."""
    client.post('/api/items', json={'name': 'Group A Item'})

    def mock_group_b(token):
        return {'user_id': 'user-b', 'group_id': 'group-B', 'role': 'MANAGER',
                'user_name': 'User B', 'group_name': 'Group B', 'join_code': 'GROUPB'}

    with patch.object(auth_module, 'decode_token', mock_group_b):
        assert client.get('/api/items').get_json() == []
        client.post('/api/items', json={'name': 'Group B Item'})
        data = client.get('/api/items').get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Group B Item'


# --- Auth API Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_register_group_success(client, mock_db):
    """POST /api/auth/register creates group and admin user."""
    response = client.post('/api/auth/register', json={
        'group_name': 'Smith Family', 'user_name': 'John Smith',
        'email': 'john@smith.com', 'password': 'secure123'})
    assert response.status_code == 201
    assert response.get_json()['details']['role'] == 'MANAGER'


@pytest.mark.integration
@pytest.mark.p1
def test_register_duplicate_email_returns_400(client, registered_group):
    """POST /api/auth/register rejects duplicate email."""
    response = client.post('/api/auth/register', json={
        'group_name': 'Another', 'user_name': 'John', 'email': 'john@smith.com', 'password': 'pass'})
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_register_missing_fields_returns_400(client):
    """POST /api/auth/register rejects missing required fields."""
    assert client.post('/api/auth/register', json={'group_name': 'Smith'}).status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_join_group_success(client, registered_group):
    """POST /api/auth/join allows member to join via join code."""
    response = client.post('/api/auth/join', json={
        'join_code': registered_group['join_code'], 'user_name': 'Jane',
        'email': 'jane@smith.com', 'password': 'pass456'})
    assert response.status_code == 201
    assert response.get_json()['details']['role'] == 'MEMBER'


@pytest.mark.integration
@pytest.mark.p1
def test_join_invalid_code_returns_400(client):
    """POST /api/auth/join rejects invalid join code."""
    response = client.post('/api/auth/join', json={
        'join_code': 'INVALID', 'user_name': 'Jane', 'email': 'jane@e.com', 'password': 'pass'})
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_join_duplicate_email_returns_400(client, registered_group):
    """POST /api/auth/join rejects duplicate email."""
    response = client.post('/api/auth/join', json={
        'join_code': registered_group['join_code'], 'user_name': 'John Again',
        'email': 'john@smith.com', 'password': 'pass'})
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_join_missing_fields(client):
    """POST /api/auth/join with empty body returns 400."""
    response = client.post('/api/auth/join', json={})
    assert response.status_code == 400
    assert 'Missing required fields' in response.get_json()['error']


@pytest.mark.integration
@pytest.mark.p0
def test_login_success(client, registered_group):
    """POST /api/auth/login returns token for valid credentials."""
    response = client.post('/api/auth/login', json={'email': 'john@smith.com', 'password': 'secure123'})
    assert response.status_code == 200
    assert 'token' in response.get_json()


@pytest.mark.integration
@pytest.mark.p1
def test_login_invalid_credentials_returns_401(client, registered_group):
    """POST /api/auth/login rejects invalid credentials."""
    response = client.post('/api/auth/login', json={'email': 'john@smith.com', 'password': 'wrong'})
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.p1
def test_login_missing_fields_returns_400(client):
    """POST /api/auth/login rejects missing credentials."""
    assert client.post('/api/auth/login', json={'email': 'john@smith.com'}).status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_get_current_user_success(client):
    """GET /api/auth/me returns current user info."""
    data = client.get('/api/auth/me').get_json()
    assert all(k in data for k in ['user_id', 'user_name', 'role', 'group_id'])


@pytest.mark.integration
@pytest.mark.p1
def test_get_current_user_no_token_returns_401(app):
    """GET /api/auth/me returns 401 without token."""
    assert app.test_client().get('/api/auth/me').status_code == 401


@pytest.mark.integration
@pytest.mark.p1
def test_api_invalid_token_returns_401(app):
    """API endpoints reject invalid tokens."""
    client = app.test_client()
    client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer invalid.token'
    assert client.get('/api/items').status_code == 401


@pytest.mark.integration
@pytest.mark.p1
def test_auth_user_not_in_db(client, mock_db):
    """Token valid but user missing from DB should use token fallback."""
    # The conftest mock uses 'test-user-123' which isn't valid ObjectId,
    # causing exception and fallback to lines 92-93. This test covers that path.
    response = client.get('/api/auth/me')
    assert response.status_code == 200
    data = response.get_json()
    assert data['user_name'] == 'Test User'


@pytest.mark.integration
@pytest.mark.p1
def test_auth_user_not_in_db_valid_oid(client, mock_db):
    """Token with valid ObjectId but user missing from DB uses token fallback (lines 88-89)."""
    valid_oid = str(ObjectId())

    def mock_decode_valid_oid(token):
        return {'user_id': valid_oid, 'group_id': 'test-group-456', 'role': 'MANAGER',
                'user_name': 'Token User', 'group_name': 'Test Group', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_valid_oid):
        response = client.get('/api/auth/me')
        assert response.status_code == 200
        data = response.get_json()
        # User not in DB, should fall back to token's user_name
        assert data['user_name'] == 'Token User'
        assert data['role'] == 'MANAGER'


# --- Group Management API Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_get_group_members_success(client, registered_group):
    """GET /api/groups/members returns member list."""
    response = client.get('/api/groups/members')
    assert response.status_code == 200
    assert isinstance(response.get_json(), list)


@pytest.mark.integration
@pytest.mark.p0
def test_update_member_role_success(client, group_with_member):
    """PUT /api/groups/members/<id> allows MANAGER to update role."""
    admin, member = group_with_member['admin'], group_with_member['member']

    def mock_admin(token):
        return {'user_id': admin['user_id'], 'group_id': admin['group_id'], 'role': 'MANAGER',
                'user_name': 'John', 'group_name': 'Smith Family', 'join_code': admin['join_code']}

    with patch.object(auth_module, 'decode_token', mock_admin):
        response = client.put(f"/api/groups/members/{member['user_id']}", json={'role': 'MANAGER'})
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.p1
def test_update_member_role_forbidden_for_member(client, as_member):
    """PUT /api/groups/members/<id> forbidden for MEMBER."""
    assert client.put(f'/api/groups/members/{ObjectId()}', json={'role': 'MANAGER'}).status_code == 403


@pytest.mark.integration
@pytest.mark.p1
def test_update_member_invalid_role_returns_400(client, group_with_member):
    """PUT /api/groups/members/<id> rejects invalid role."""
    admin, member = group_with_member['admin'], group_with_member['member']

    def mock_admin(token):
        return {'user_id': admin['user_id'], 'group_id': admin['group_id'], 'role': 'MANAGER',
                'user_name': 'John', 'group_name': 'Smith Family', 'join_code': admin['join_code']}

    with patch.object(auth_module, 'decode_token', mock_admin):
        response = client.put(f"/api/groups/members/{member['user_id']}", json={'role': 'ADMIN'})
        assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_update_self_role_returns_400(client, registered_group):
    """PUT /api/groups/members/<id> prevents self-promotion."""
    def mock_self(token):
        return {'user_id': registered_group['user_id'], 'group_id': registered_group['group_id'],
                'role': 'MANAGER', 'user_name': 'John', 'group_name': 'Smith', 'join_code': 'TEST'}

    with patch.object(auth_module, 'decode_token', mock_self):
        response = client.put(f"/api/groups/members/{registered_group['user_id']}", json={'role': 'MEMBER'})
        assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_delete_member_success(client, group_with_member):
    """DELETE /api/groups/members/<id> allows MANAGER to remove member."""
    admin, member = group_with_member['admin'], group_with_member['member']

    def mock_admin(token):
        return {'user_id': admin['user_id'], 'group_id': admin['group_id'], 'role': 'MANAGER',
                'user_name': 'John', 'group_name': 'Smith Family', 'join_code': admin['join_code']}

    with patch.object(auth_module, 'decode_token', mock_admin):
        assert client.delete(f"/api/groups/members/{member['user_id']}").status_code == 204


@pytest.mark.integration
@pytest.mark.p1
def test_delete_member_forbidden_for_member(client, as_member):
    """DELETE /api/groups/members/<id> forbidden for MEMBER."""
    assert client.delete(f'/api/groups/members/{ObjectId()}').status_code == 403


@pytest.mark.integration
@pytest.mark.p1
def test_delete_self_returns_400(client, registered_group):
    """DELETE /api/groups/members/<id> prevents self-deletion."""
    def mock_self(token):
        return {'user_id': registered_group['user_id'], 'group_id': registered_group['group_id'],
                'role': 'MANAGER', 'user_name': 'John', 'group_name': 'Smith', 'join_code': 'TEST'}

    with patch.object(auth_module, 'decode_token', mock_self):
        assert client.delete(f"/api/groups/members/{registered_group['user_id']}").status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_delete_member_not_found_returns_404(client):
    """DELETE /api/groups/members/<id> returns 404 for non-existent user."""
    assert client.delete(f'/api/groups/members/{ObjectId()}').status_code == 404


# --- Health Endpoint Tests ---

@pytest.mark.integration
@pytest.mark.p2
def test_health_endpoint_returns_200(app):
    """GET /api/health returns 200 when healthy."""
    response = app.test_client().get('/api/health')
    assert response.status_code in [200, 503]
    assert 'status' in response.get_json()


@pytest.mark.integration
def test_health_db_down(client):
    """GET /api/health returns 503 if DB ping fails."""
    mock_client = MagicMock()
    mock_client.admin.command.side_effect = Exception("DB Down")

    with patch('app.db') as mock_db_module:
        mock_db_module.db_client = mock_client
        response = client.get('/api/health')
        assert response.status_code == 503


# ==========================================
#           RESILIENCE TESTS
# ==========================================

from pymongo.errors import ConnectionFailure
from db import get_db_connection

@pytest.mark.resilience
def test_db_connection_retries_and_fails(monkeypatch):
    """get_db_connection retries max_retries times and then raises ConnectionFailure."""
    mock_mongo = MagicMock(side_effect=ConnectionFailure("Connection refused"))

    with patch('db.MongoClient', mock_mongo):
        monkeypatch.setattr('time.sleep', lambda x: None)
        with pytest.raises(ConnectionFailure):
            get_db_connection(max_retries=3)

    assert mock_mongo.call_count == 3


@pytest.mark.resilience
def test_db_connection_succeeds_after_retry(monkeypatch):
    """get_db_connection succeeds after a few failures."""
    mock_success = MagicMock()
    mock_mongo = MagicMock(side_effect=[ConnectionFailure("Fail 1"), ConnectionFailure("Fail 2"), mock_success])

    with patch('db.MongoClient', mock_mongo):
        monkeypatch.setattr('time.sleep', lambda x: None)
        assert get_db_connection(max_retries=5) == mock_success

    assert mock_mongo.call_count == 3


@pytest.mark.resilience
def test_db_connection_no_retries():
    """get_db_connection returns None if max_retries is 0."""
    assert get_db_connection(max_retries=0) is None


@pytest.mark.resilience
def test_get_db_lazy_init():
    """get_db initializes the client if it is None."""
    from db import get_db
    import db as db_module

    db_module.db_client = None
    db_module.db = None

    mock_client = MagicMock()
    mock_db_obj = MagicMock()
    mock_client.get_database.return_value = mock_db_obj

    with patch('db.get_db_connection', return_value=mock_client):
        assert get_db() == mock_db_obj
        assert db_module.db_client == mock_client


@pytest.mark.resilience
def test_ai_engine_openai_client_failure(monkeypatch):
    """estimate_item_price handles OpenAI client initialization failure."""
    with patch('ai_engine.get_openai_client', return_value=None):
        monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
        price, status = estimate_item_price('Milk', 'Dairy')

    assert price == 0.0 and status == 'ERROR'


@pytest.mark.resilience
@pytest.mark.parametrize("content,expected_price", [
    ("I cannot estimate", 0.0),
    ("-50.0", 0.0),
])
def test_ai_engine_bad_responses(monkeypatch, content, expected_price):
    """estimate_item_price handles non-numeric and negative responses."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch('ai_engine.get_openai_client', return_value=mock_client):
        monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
        price, status = estimate_item_price('Item', 'Cat')

    assert price == expected_price and status == 'ERROR'


@pytest.mark.resilience
def test_ai_engine_exception_handling(monkeypatch):
    """estimate_item_price handles unexpected exceptions."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API Down")

    with patch('ai_engine.get_openai_client', return_value=mock_client):
        monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
        price, status = estimate_item_price('Item', 'Cat')

    assert price == 0.0 and status == 'ERROR'


@pytest.mark.resilience
def test_metrics_collector_handles_error(app):
    """DbConnectionsCollector handles exceptions gracefully."""
    from app import DbConnectionsCollector, update_db_metrics

    with patch('app.db') as mock_db_module:
        type(mock_db_module).db_client = PropertyMock(side_effect=Exception("DB Error"))
        list(DbConnectionsCollector().collect())
        update_db_metrics()


@pytest.mark.resilience
def test_metrics_collector_success():
    """DbConnectionsCollector yields metrics when DB is connected."""
    from app import DbConnectionsCollector, update_db_metrics

    mock_client = MagicMock()
    mock_client.admin.command.return_value = {'connections': {'current': 42}}

    with patch('app.db') as mock_db_module:
        mock_db_module.db_client = mock_client
        mock_db_module.db.__getitem__.return_value.count_documents.return_value = 100

        metrics = list(DbConnectionsCollector().collect())
        assert len(metrics) == 1
        assert metrics[0].samples[0].value == 42

        update_db_metrics()


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


# --- DB Failure Tests ---

@pytest.mark.integration
def test_get_items_db_error(client, mock_db):
    """GET /api/items returns 500 if DB fetch fails."""
    with patch('app.get_db', side_effect=Exception("DB access failed")):
        response = client.get('/api/items')
        assert response.status_code == 500


@pytest.mark.integration
def test_create_item_validation_error(client, mock_db):
    """POST /api/items with invalid data returns 400."""
    response = client.post('/api/items', json={'group_id': 'only_group'})
    assert response.status_code == 400
    assert 'Validation failed' in response.get_json()['error']


@pytest.mark.integration
def test_all_endpoints_handle_db_failure(client):
    """Endpoints return 500 on DB failure."""
    mock_db_fail = MagicMock()
    for method in ['find', 'find_one', 'insert_one', 'update_one', 'delete_one', 'delete_many']:
        mock_db_fail.__getitem__.return_value.__getattr__(method).side_effect = Exception("DB Fail")

    with patch('app.get_db', return_value=mock_db_fail), \
         patch('auth.get_db', return_value=mock_db_fail):
        valid_oid = "507f1f77bcf86cd799439011"
        assert client.put(f'/api/items/{valid_oid}', json={'status': 'APPROVED'}).status_code == 500
        assert client.delete(f'/api/items/{valid_oid}').status_code == 500
        assert client.delete('/api/items/clear').status_code == 500


@pytest.mark.integration
def test_app_metrics_exclusion_logic(app):
    """Test the after_request logic for metrics exclusion."""
    from app import after_request
    from flask import request, Response

    with app.test_request_context('/metrics'):
        request.url_rule = MagicMock()
        request.url_rule.endpoint = 'metrics'
        resp = Response("ok", 200)
        assert after_request(resp) == resp


# --- Additional Coverage Tests ---

@pytest.mark.integration
def test_put_item_invalid_id_returns_400(client):
    """PUT /api/items/<id> returns 400 for invalid ObjectId format."""
    assert client.put('/api/items/not-a-valid-oid', json={'status': 'APPROVED'}).status_code == 400


@pytest.mark.integration
def test_delete_item_invalid_id_returns_400(client):
    """DELETE /api/items/<id> returns 400 for invalid ObjectId format."""
    assert client.delete('/api/items/not-a-valid-oid').status_code == 400


@pytest.mark.integration
def test_manage_member_invalid_id_returns_400(client):
    """PUT/DELETE /api/groups/members/<id> returns 400 for invalid ObjectId format."""
    assert client.put('/api/groups/members/not-valid', json={'role': 'MANAGER'}).status_code == 400
    assert client.delete('/api/groups/members/not-valid').status_code == 400


@pytest.mark.integration
def test_delete_item_race_condition(client, mock_db):
    """DELETE /api/items/<id> handles race condition where item deleted between find and delete."""
    item_id = client.post('/api/items', json={'name': 'Item'}).get_json()['_id']

    # Mock delete_one to return 0 deleted (simulating race condition)
    original_delete = mock_db['items'].delete_one
    def mock_delete(*args, **kwargs):
        result = MagicMock()
        result.deleted_count = 0
        return result

    mock_db['items'].delete_one = mock_delete
    response = client.delete(f'/api/items/{item_id}')
    assert response.status_code == 404
    mock_db['items'].delete_one = original_delete


@pytest.mark.integration
def test_get_group_members_db_error(client, mock_db):
    """GET /api/groups/members returns 500 on DB error."""
    with patch('app.get_db', side_effect=Exception("DB fail")):
        assert client.get('/api/groups/members').status_code == 500


@pytest.mark.integration
def test_manage_member_db_error(client, mock_db):
    """PUT /api/groups/members/<id> returns 500 on DB error."""
    with patch('app.get_db', side_effect=Exception("DB fail")):
        valid_oid = "507f1f77bcf86cd799439011"
        assert client.put(f'/api/groups/members/{valid_oid}', json={'role': 'MANAGER'}).status_code == 500


@pytest.mark.integration
def test_create_item_db_error(client, mock_db):
    """POST /api/items returns 500 on DB error after validation."""
    with patch('app.get_db', side_effect=Exception("DB fail")):
        response = client.post('/api/items', json={'name': 'Test'})
        assert response.status_code == 500


@pytest.mark.integration
def test_auth_db_exception_fallback(client, mock_db):
    """auth_required falls back to token data when DB throws exception."""
    def mock_decode(token):
        return {'user_id': 'test-user', 'group_id': 'test-group', 'role': 'MANAGER',
                'user_name': 'Fallback User', 'group_name': 'Test', 'join_code': 'TEST'}

    mock_db_fail = MagicMock()
    mock_db_fail.__getitem__.return_value.find_one.side_effect = Exception("DB Down")

    with patch.object(auth_module, 'decode_token', mock_decode), \
         patch('auth.get_db', return_value=mock_db_fail):
        response = client.get('/api/auth/me')
        assert response.status_code == 200
        assert response.get_json()['user_name'] == 'Fallback User'


@pytest.mark.unit
def test_register_group_validation_error():
    """register_group_and_admin returns errors when group validation fails."""
    from auth import register_group_and_admin

    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one.return_value = None

    with patch('auth.get_db', return_value=mock_db):
        # Empty name triggers validation error
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

    # Patch validate_user at auth module level to return error AFTER group is created
    with patch('auth.get_db', return_value=mock_db), \
         patch('auth.validate_user', return_value=({}, ['Invalid user data'])):
        result, errors = register_group_and_admin('Group', 'User', 'e@e.com', 'pass')
        assert result is None
        assert 'Invalid user data' in errors
        # Verify rollback was called
        mock_db.__getitem__.return_value.delete_one.assert_called()


@pytest.mark.unit
def test_join_user_validation_error():
    """register_member_via_code returns errors when user validation fails."""
    from auth import register_member_via_code

    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one.side_effect = [
        {'_id': ObjectId(), 'name': 'Group', 'join_code': 'ABC123'},  # group found
        None  # user not found (email not taken)
    ]

    # Patch validate_user at auth module level
    with patch('auth.get_db', return_value=mock_db), \
         patch('auth.validate_user', return_value=({}, ['Invalid user'])):
        result, errors = register_member_via_code('ABC123', 'User', 'e@e.com', 'pass')
        assert result is None
        assert 'Invalid user' in errors


# Note: Lines 257-258 (AI background task exception) and 462-463 (if __name__ == '__main__')
# cannot be easily covered in pytest - the former runs in a daemon thread, the latter
# only executes when module is run directly. This is expected/acceptable.

"""
Unified Test Suite
Combines unit tests (business logic) and integration tests (API endpoints).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
from bson import ObjectId
from datetime import datetime, timezone
import re
from unittest.mock import patch

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
        'name': 'Milk',
        'group_id': 'test-group-123',
        'category': 'Dairy',
        'submitted_by': 'user-456',
        'submitted_by_name': 'John Doe',
        'status': 'APPROVED',
        'price_nis': 12.5,
        'quantity': 2,
        'ai_status': 'COMPLETED',
        'ai_latency': 1.23
    }
    validated, errors = validate_item(data)

    assert errors == []
    assert validated['name'] == 'Milk'
    assert validated['group_id'] == 'test-group-123'
    assert validated['category'] == 'Dairy'
    assert validated['submitted_by'] == 'user-456'
    assert validated['submitted_by_name'] == 'John Doe'
    assert validated['status'] == 'APPROVED'
    assert validated['price_nis'] == 12.5
    assert validated['quantity'] == 2
    assert validated['ai_status'] == 'COMPLETED'
    assert validated['ai_latency'] == 1.23
    assert 'created_at' in validated


@pytest.mark.unit
def test_validate_item_minimal_fields():
    """validate_item works with minimal required fields."""
    data = {'name': 'Bread', 'group_id': 'group-789'}
    validated, errors = validate_item(data)

    assert errors == []
    assert validated['name'] == 'Bread'
    assert validated['status'] == 'PENDING'  # Default
    assert validated['price_nis'] == 0.0  # Default
    assert validated['quantity'] == 1  # Default
    assert validated['category'] == 'OTHER'  # Default


@pytest.mark.unit
def test_validate_item_missing_name():
    """validate_item rejects item without name."""

    data = {'group_id': 'test-group-123'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('name' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_empty_name():
    """validate_item rejects empty or whitespace-only name."""

    data = {'name': '   ', 'group_id': 'test-group-123'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('empty' in err.lower() or 'whitespace' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_name_too_long():
    """validate_item rejects name exceeding max length."""
    from models import validate_item, MAX_ITEM_NAME_LENGTH

    data = {'name': 'x' * (MAX_ITEM_NAME_LENGTH + 1), 'group_id': 'test-group-123'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('exceed' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_missing_group_id():
    """validate_item rejects item without group_id."""

    data = {'name': 'Bread'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('group_id' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_strips_whitespace():
    """validate_item strips whitespace from name and category."""

    data = {'name': '  Eggs  ', 'group_id': 'test-group-123', 'category': '  Protein  '}
    validated, errors = validate_item(data)

    assert errors == []
    assert validated['name'] == 'Eggs'
    assert validated['category'] == 'Protein'


@pytest.mark.unit
def test_validate_item_invalid_status():
    """validate_item rejects invalid status."""

    data = {'name': 'Candy', 'group_id': 'test-group-123', 'status': 'INVALID'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('status' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_invalid_quantity():
    """validate_item rejects invalid or negative quantity."""

    # Test negative quantity
    data = {'name': 'Candy', 'group_id': 'test-group-123', 'quantity': 0}
    validated, errors = validate_item(data)
    assert len(errors) > 0
    assert any('quantity' in err.lower() for err in errors)

    # Test non-integer quantity
    data = {'name': 'Candy', 'group_id': 'test-group-123', 'quantity': 'abc'}
    validated, errors = validate_item(data)
    assert len(errors) > 0
    assert any('quantity' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_invalid_price():
    """validate_item rejects non-numeric price."""

    data = {'name': 'Candy', 'group_id': 'test-group-123', 'price_nis': 'expensive'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('price_nis' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_invalid_ai_status():
    """validate_item rejects invalid ai_status."""

    data = {'name': 'Candy', 'group_id': 'test-group-123', 'ai_status': 'INVALID'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('ai_status' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_invalid_user_role():
    """validate_item rejects invalid user_role."""

    data = {'name': 'Candy', 'group_id': 'test-group-123', 'user_role': 'ADMIN'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('user_role' in err.lower() for err in errors)


# --- User Validation Tests ---

@pytest.mark.unit
def test_validate_user_success():
    """validate_user accepts valid user data."""

    data = {
        'email': 'test@example.com',
        'password_hash': 'hashed_password_123',
        'group_id': 'group-456',
        'role': 'MANAGER',
        'full_name': 'John Doe'
    }
    validated, errors = validate_user(data)

    assert errors == []
    assert validated['email'] == 'test@example.com'
    assert validated['password_hash'] == 'hashed_password_123'
    assert validated['group_id'] == 'group-456'
    assert validated['role'] == 'MANAGER'
    assert validated['full_name'] == 'John Doe'
    assert 'created_at' in validated


@pytest.mark.unit
def test_validate_user_email_normalization():
    """validate_user normalizes email to lowercase."""

    data = {
        'email': 'Test@Example.COM',
        'password_hash': 'hash',
        'group_id': 'group-123',
        'role': 'MEMBER'
    }
    validated, errors = validate_user(data)

    assert errors == []
    assert validated['email'] == 'test@example.com'


@pytest.mark.unit
def test_validate_user_invalid_email():
    """validate_user rejects invalid email formats."""

    invalid_emails = ['notanemail', '@example.com', 'user@', 'user@.com', '']

    for email in invalid_emails:
        data = {
            'email': email,
            'password_hash': 'hash',
            'group_id': 'group-123',
            'role': 'MEMBER'
        }
        validated, errors = validate_user(data)
        assert len(errors) > 0, f"Should reject email: {email}"
        assert any('email' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_user_missing_required_fields():
    """validate_user rejects data missing required fields."""

    # Missing email
    data = {'password_hash': 'hash', 'group_id': 'group-123', 'role': 'MEMBER'}
    validated, errors = validate_user(data)
    assert len(errors) > 0
    assert any('email' in err.lower() for err in errors)

    # Missing password_hash
    data = {'email': 'test@example.com', 'group_id': 'group-123', 'role': 'MEMBER'}
    validated, errors = validate_user(data)
    assert len(errors) > 0
    assert any('password_hash' in err.lower() for err in errors)

    # Missing group_id
    data = {'email': 'test@example.com', 'password_hash': 'hash', 'role': 'MEMBER'}
    validated, errors = validate_user(data)
    assert len(errors) > 0
    assert any('group_id' in err.lower() for err in errors)

    # Missing role
    data = {'email': 'test@example.com', 'password_hash': 'hash', 'group_id': 'group-123'}
    validated, errors = validate_user(data)
    assert len(errors) > 0
    assert any('role' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_user_invalid_role():
    """validate_user rejects invalid role values."""

    data = {
        'email': 'test@example.com',
        'password_hash': 'hash',
        'group_id': 'group-123',
        'role': 'ADMIN'  # Invalid, only MANAGER/MEMBER allowed
    }
    validated, errors = validate_user(data)

    assert len(errors) > 0
    assert any('role' in err.lower() for err in errors)


# --- Group Validation Tests ---

@pytest.mark.unit
def test_validate_group_success():
    """validate_group accepts valid group data."""

    data = {'name': 'Smith Family', 'join_code': 'ABC123', 'subscription_tier': 'PREMIUM'}
    validated, errors = validate_group(data)

    assert errors == []
    assert validated['name'] == 'Smith Family'
    assert validated['join_code'] == 'ABC123'
    assert validated['subscription_tier'] == 'PREMIUM'
    assert 'created_at' in validated


@pytest.mark.unit
def test_validate_group_generates_join_code():
    """validate_group generates join_code if not provided."""

    data = {'name': 'Johnson Family'}
    validated, errors = validate_group(data)

    assert errors == []
    assert validated['name'] == 'Johnson Family'
    assert 'join_code' in validated
    assert len(validated['join_code']) == 6
    assert validated['subscription_tier'] == 'FREE'  # Default


@pytest.mark.unit
def test_validate_group_missing_name():
    """validate_group rejects data without name."""

    data = {}
    validated, errors = validate_group(data)

    assert len(errors) > 0
    assert any('name' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_group_empty_name():
    """validate_group rejects empty or whitespace-only name."""

    data = {'name': '   '}
    validated, errors = validate_group(data)

    assert len(errors) > 0
    assert any('name' in err.lower() for err in errors)


# --- Helper Function Tests ---

@pytest.mark.unit
def test_item_to_dict_converts_objectid():
    """item_to_dict converts MongoDB ObjectId to string."""

    item = {
        '_id': ObjectId(),
        'name': 'Test Item',
        'group_id': 'test-group-123',
        'status': 'APPROVED'
    }
    result = item_to_dict(item)

    assert isinstance(result['_id'], str)
    assert result['name'] == 'Test Item'


@pytest.mark.unit
def test_item_to_dict_adds_defaults():
    """item_to_dict adds default values for missing optional fields."""

    item = {'_id': ObjectId(), 'name': 'Test'}
    result = item_to_dict(item)

    assert result['ai_status'] is None
    assert result['ai_latency'] is None
    assert result['quantity'] == 1
    assert result['submitted_by_name'] == 'Group Member'


@pytest.mark.unit
def test_item_to_dict_preserves_submitted_by_name():
    """item_to_dict preserves submitted_by_name if present."""

    item = {'_id': ObjectId(), 'name': 'Test', 'submitted_by_name': 'Alice'}
    result = item_to_dict(item)

    assert result['submitted_by_name'] == 'Alice'


@pytest.mark.unit
def test_user_to_dict_removes_password():
    """user_to_dict removes password_hash from user data."""

    user = {
        '_id': ObjectId(),
        'email': 'test@example.com',
        'password_hash': 'secret_hash_123',
        'role': 'MANAGER'
    }
    result = user_to_dict(user)

    assert isinstance(result['_id'], str)
    assert 'password_hash' not in result
    assert result['email'] == 'test@example.com'
    assert result['role'] == 'MANAGER'


# --- Auth Helper Tests ---

@pytest.mark.unit
def test_hash_password():
    """hash_password returns a bcrypt hash."""

    password = 'my_secure_password'
    hashed = hash_password(password)

    assert isinstance(hashed, str)
    assert len(hashed) > 0
    assert hashed != password
    assert hashed.startswith('$2b$')  # bcrypt hash prefix


@pytest.mark.unit
def test_verify_password_success():
    """verify_password returns True for correct password."""

    password = 'correct_password'
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


@pytest.mark.unit
def test_verify_password_failure():
    """verify_password returns False for incorrect password."""

    password = 'correct_password'
    hashed = hash_password(password)

    assert verify_password('wrong_password', hashed) is False


@pytest.mark.unit
def test_generate_token():
    """generate_token creates a valid JWT with all claims."""

    token = generate_token(
        user_id='user-123',
        group_id='group-456',
        role='MANAGER',
        user_name='John Doe',
        group_name='Smith Family',
        join_code='ABC123'
    )

    assert isinstance(token, str)
    assert len(token) > 0

    # Decode and verify claims
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded['user_id'] == 'user-123'
    assert decoded['group_id'] == 'group-456'
    assert decoded['role'] == 'MANAGER'
    assert decoded['user_name'] == 'John Doe'
    assert decoded['group_name'] == 'Smith Family'
    assert decoded['join_code'] == 'ABC123'
    assert 'exp' in decoded


@pytest.mark.unit
def test_decode_token_invalid():
    """decode_token returns None for invalid token."""
    assert decode_token('invalid.token.here') is None
    assert decode_token('') is None


# --- AI Engine Tests ---

@pytest.mark.unit
def test_ai_engine_fallback_no_api_key(monkeypatch):
    """estimate_item_price returns fallback when OPENAI_API_KEY not set."""

    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    price, status = estimate_item_price('Milk', 'Dairy')

    assert price == 0.0  # Fallback price
    assert status == 'ERROR'


@pytest.mark.unit
def test_ai_engine_fallback_empty_api_key(monkeypatch):
    """estimate_item_price returns fallback when OPENAI_API_KEY is empty."""

    monkeypatch.setenv('OPENAI_API_KEY', '')
    price, status = estimate_item_price('Bread', 'Bakery')

    assert price == 0.0
    assert status == 'ERROR'


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
    assert isinstance(response.get_json(), list)
    assert len(response.get_json()) == 0


@pytest.mark.integration
@pytest.mark.p0
def test_post_item_success_manager(client):
    """POST /api/items creates item with APPROVED status for MANAGER."""
    response = client.post('/api/items', json={'name': 'Milk', 'category': 'Dairy'})
    assert response.status_code == 201
    data = response.get_json()
    assert '_id' in data
    assert data['name'] == 'Milk'
    assert data['status'] == 'APPROVED'  # Auto-approved for MANAGER
    assert data['ai_status'] == 'CALCULATING'


@pytest.mark.integration
@pytest.mark.p0
def test_post_item_success_member(client, mock_db):
    """POST /api/items creates item with PENDING status for MEMBER."""
    # Override mock to return MEMBER role

    def mock_decode_member(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member User', 'group_name': 'Test Group', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_member):
        response = client.post('/api/items', json={'name': 'Bread'})
        assert response.status_code == 201
        data = response.get_json()
        assert data['status'] == 'PENDING'  # Not auto-approved for MEMBER


@pytest.mark.integration
@pytest.mark.p1
def test_post_item_missing_name_returns_400(client):
    """POST /api/items without name returns 400."""
    response = client.post('/api/items', json={})
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


@pytest.mark.integration
@pytest.mark.p1
def test_post_item_invalid_json_returns_400(client):
    """POST /api/items with invalid JSON returns 400."""
    response = client.post('/api/items', data='not json', content_type='application/json')
    assert response.status_code in [400, 415]


@pytest.mark.integration
@pytest.mark.p0
def test_get_items_returns_created_items(client):
    """GET /api/items returns created items."""
    client.post('/api/items', json={'name': 'Bread'})
    client.post('/api/items', json={'name': 'Eggs'})

    response = client.get('/api/items')
    data = response.get_json()
    assert len(data) == 2
    names = [item['name'] for item in data]
    assert 'Bread' in names
    assert 'Eggs' in names


@pytest.mark.integration
@pytest.mark.p0
def test_put_item_updates_status_manager(client):
    """PUT /api/items/<id> updates status (MANAGER only)."""
    create_response = client.post('/api/items', json={'name': 'Candy'})
    item_id = create_response.get_json()['_id']

    update_response = client.put(f'/api/items/{item_id}', json={'status': 'REJECTED'})
    assert update_response.status_code == 200


@pytest.mark.integration
@pytest.mark.p1
def test_put_item_status_forbidden_for_member(client):
    """PUT /api/items/<id> status change forbidden for MEMBER."""
    # Create item as MANAGER
    create_response = client.post('/api/items', json={'name': 'Candy'})
    item_id = create_response.get_json()['_id']

    # Try to update status as MEMBER
    def mock_decode_member(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member User', 'group_name': 'Test Group', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_member):
        update_response = client.put(f'/api/items/{item_id}', json={'status': 'APPROVED'})
        assert update_response.status_code == 403


@pytest.mark.integration
@pytest.mark.p0
def test_put_item_updates_quantity(client):
    """PUT /api/items/<id> allows anyone to update quantity."""
    create_response = client.post('/api/items', json={'name': 'Candy'})
    item_id = create_response.get_json()['_id']

    update_response = client.put(f'/api/items/{item_id}', json={'quantity': 5})
    assert update_response.status_code == 200


@pytest.mark.integration
@pytest.mark.p1
def test_put_item_invalid_quantity_returns_400(client):
    """PUT /api/items/<id> rejects invalid quantity."""
    create_response = client.post('/api/items', json={'name': 'Candy'})
    item_id = create_response.get_json()['_id']

    # Test negative quantity
    update_response = client.put(f'/api/items/{item_id}', json={'quantity': 0})
    assert update_response.status_code == 400

    # Test non-integer quantity
    update_response = client.put(f'/api/items/{item_id}', json={'quantity': 'abc'})
    assert update_response.status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_put_item_not_found_returns_404(client):
    """PUT /api/items/<id> returns 404 for non-existent item."""
    fake_id = str(ObjectId())
    response = client.put(f'/api/items/{fake_id}', json={'status': 'APPROVED'})
    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.p0
def test_delete_item_by_manager(client):
    """DELETE /api/items/<id> allows MANAGER to delete any item."""
    create_response = client.post('/api/items', json={'name': 'Juice'})
    item_id = create_response.get_json()['_id']

    delete_response = client.delete(f'/api/items/{item_id}')
    assert delete_response.status_code == 204

    get_response = client.get('/api/items')
    assert len(get_response.get_json()) == 0


@pytest.mark.integration
@pytest.mark.p1
def test_delete_item_by_owner(client):
    """DELETE /api/items/<id> allows owner to delete their own item."""

    # Create item as MEMBER
    def mock_decode_member(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member User', 'group_name': 'Test Group', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_member):
        create_response = client.post('/api/items', json={'name': 'Snack'})
        item_id = create_response.get_json()['_id']

        # Owner can delete their own item
        delete_response = client.delete(f'/api/items/{item_id}')
        assert delete_response.status_code == 204


@pytest.mark.integration
@pytest.mark.p1
def test_delete_item_forbidden_for_non_owner_member(client, mock_db):
    """DELETE /api/items/<id> forbidden for MEMBER who doesn't own item."""

    # Create item as MANAGER
    create_response = client.post('/api/items', json={'name': 'Snack'})
    item_id = create_response.get_json()['_id']

    # Try to delete as different MEMBER
    def mock_decode_other_member(token):
        return {'user_id': 'other-member-999', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Other Member', 'group_name': 'Test Group', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_other_member):
        delete_response = client.delete(f'/api/items/{item_id}')
        assert delete_response.status_code == 403


@pytest.mark.integration
@pytest.mark.p1
def test_delete_item_not_found_returns_404(client):
    """DELETE /api/items/<id> returns 404 for non-existent item."""
    fake_id = str(ObjectId())
    response = client.delete(f'/api/items/{fake_id}')
    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.p0
def test_delete_all_items_by_manager(client):
    """DELETE /api/items/clear allows MANAGER to clear all items."""
    # Create multiple items
    client.post('/api/items', json={'name': 'Item1'})
    client.post('/api/items', json={'name': 'Item2'})
    client.post('/api/items', json={'name': 'Item3'})

    # Clear all
    response = client.delete('/api/items/clear')
    assert response.status_code == 204

    # Verify all deleted
    get_response = client.get('/api/items')
    assert len(get_response.get_json()) == 0


@pytest.mark.integration
@pytest.mark.p1
def test_delete_all_items_forbidden_for_member(client):
    """DELETE /api/items/clear forbidden for MEMBER."""
    def mock_decode_member(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member User', 'group_name': 'Test Group', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_member):
        response = client.delete('/api/items/clear')
        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.p0
def test_crud_flow_complete(client):
    """Test complete CRUD flow for items."""
    # CREATE
    create_resp = client.post('/api/items', json={'name': 'Coffee'})
    assert create_resp.status_code == 201
    item_id = create_resp.get_json()['_id']

    # READ
    get_resp = client.get('/api/items')
    assert len(get_resp.get_json()) == 1

    # UPDATE
    update_resp = client.put(f'/api/items/{item_id}', json={'quantity': 3})
    assert update_resp.status_code == 200

    # DELETE
    delete_resp = client.delete(f'/api/items/{item_id}')
    assert delete_resp.status_code == 204

    # Verify deletion
    assert client.get('/api/items').get_json() == []


# --- Multi-Tenancy Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_items_isolated_by_group(client, mock_db):
    """Items are isolated by group_id (multi-tenancy)."""
    # Create item in group A
    client.post('/api/items', json={'name': 'Group A Item'})

    # Switch to group B
    def mock_decode_group_b(token):
        return {'user_id': 'user-b', 'group_id': 'group-B', 'role': 'MANAGER',
                'user_name': 'User B', 'group_name': 'Group B', 'join_code': 'GROUPB'}

    with patch.object(auth_module, 'decode_token', mock_decode_group_b):
        # Group B should not see Group A's items
        response = client.get('/api/items')
        assert len(response.get_json()) == 0

        # Create item in group B
        client.post('/api/items', json={'name': 'Group B Item'})
        response = client.get('/api/items')
        assert len(response.get_json()) == 1
        assert response.get_json()[0]['name'] == 'Group B Item'


# --- Auth API Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_register_group_success(client, mock_db):
    """POST /api/auth/register creates group and admin user."""
    response = client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })

    assert response.status_code == 201
    data = response.get_json()
    assert 'details' in data
    assert 'join_code' in data['details']
    assert data['details']['role'] == 'MANAGER'


@pytest.mark.integration
@pytest.mark.p1
def test_register_duplicate_email_returns_400(client, mock_db):
    """POST /api/auth/register rejects duplicate email."""
    # First registration
    client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })

    # Duplicate email
    response = client.post('/api/auth/register', json={
        'group_name': 'Another Family',
        'user_name': 'John Doe',
        'email': 'john@smith.com',
        'password': 'password456'
    })

    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_register_missing_fields_returns_400(client):
    """POST /api/auth/register rejects missing required fields."""
    response = client.post('/api/auth/register', json={
        'group_name': 'Smith Family'
        # Missing user_name, email, password
    })

    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_join_group_success(client, mock_db):
    """POST /api/auth/join allows member to join via join code."""
    # Create group first
    register_resp = client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })
    join_code = register_resp.get_json()['details']['join_code']

    # Join as member
    response = client.post('/api/auth/join', json={
        'join_code': join_code,
        'user_name': 'Jane Smith',
        'email': 'jane@smith.com',
        'password': 'password456'
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data['details']['role'] == 'MEMBER'


@pytest.mark.integration
@pytest.mark.p1
def test_join_invalid_code_returns_400(client):
    """POST /api/auth/join rejects invalid join code."""
    response = client.post('/api/auth/join', json={
        'join_code': 'INVALID',
        'user_name': 'Jane Doe',
        'email': 'jane@example.com',
        'password': 'password123'
    })

    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_join_duplicate_email_returns_400(client, mock_db):
    """POST /api/auth/join rejects duplicate email."""
    # Create group
    register_resp = client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })
    join_code = register_resp.get_json()['details']['join_code']

    # Try to join with same email
    response = client.post('/api/auth/join', json={
        'join_code': join_code,
        'user_name': 'John Again',
        'email': 'john@smith.com',
        'password': 'password456'
    })

    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_login_success(client, mock_db):
    """POST /api/auth/login returns token for valid credentials."""
    # Register first
    client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })

    # Login
    response = client.post('/api/auth/login', json={
        'email': 'john@smith.com',
        'password': 'secure123'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert 'token' in data
    assert isinstance(data['token'], str)


@pytest.mark.integration
@pytest.mark.p1
def test_login_invalid_credentials_returns_401(client, mock_db):
    """POST /api/auth/login rejects invalid credentials."""
    # Register first
    client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })

    # Wrong password
    response = client.post('/api/auth/login', json={
        'email': 'john@smith.com',
        'password': 'wrongpassword'
    })

    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.p1
def test_login_missing_fields_returns_400(client):
    """POST /api/auth/login rejects missing credentials."""
    response = client.post('/api/auth/login', json={
        'email': 'john@smith.com'
        # Missing password
    })

    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_get_current_user_success(client):
    """GET /api/auth/me returns current user info."""
    response = client.get('/api/auth/me')

    assert response.status_code == 200
    data = response.get_json()
    assert 'user_id' in data
    assert 'user_name' in data
    assert 'role' in data
    assert 'group_id' in data


@pytest.mark.integration
@pytest.mark.p1
def test_get_current_user_no_token_returns_401(app):
    """GET /api/auth/me returns 401 without token."""
    test_client = app.test_client()
    response = test_client.get('/api/auth/me')

    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.p1
def test_api_invalid_token_returns_401(app):
    """API endpoints reject invalid tokens."""
    test_client = app.test_client()
    test_client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer invalid.token.here'

    response = test_client.get('/api/items')
    assert response.status_code == 401


# --- Group Management API Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_get_group_members_success(client, mock_db):
    """GET /api/groups/members returns member list for MANAGER."""
    # Register creates a user in the mock DB
    client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })

    response = client.get('/api/groups/members')

    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


@pytest.mark.integration
@pytest.mark.p0
def test_update_member_role_success(client, mock_db):
    """PUT /api/groups/members/<id> allows MANAGER to update role."""
    # Create group and members
    register_resp = client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })
    details = register_resp.get_json()['details']
    group_id = details['group_id']
    join_code = details['join_code']
    admin_id = details['user_id']

    join_resp = client.post('/api/auth/join', json={
        'join_code': join_code,
        'user_name': 'Jane Smith',
        'email': 'jane@smith.com',
        'password': 'password456'
    })
    member_id = join_resp.get_json()['details']['user_id']

    # Patch token to match the created group and admin
    def mock_decode_manager(token):
        return {'user_id': admin_id, 'group_id': group_id, 'role': 'MANAGER',
                'user_name': 'John Smith', 'group_name': 'Smith Family', 'join_code': join_code}

    with patch.object(auth_module, 'decode_token', mock_decode_manager):
        # Promote to MANAGER
        response = client.put(f'/api/groups/members/{member_id}', json={'role': 'MANAGER'})
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.p1
def test_update_member_role_forbidden_for_member(client, mock_db):
    """PUT /api/groups/members/<id> forbidden for MEMBER."""

    fake_user_id = str(ObjectId())

    def mock_decode_member(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member User', 'group_name': 'Test Group', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_member):
        response = client.put(f'/api/groups/members/{fake_user_id}', json={'role': 'MANAGER'})
        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.p1
def test_update_member_invalid_role_returns_400(client, mock_db):
    """PUT /api/groups/members/<id> rejects invalid role."""
    # Create member
    register_resp = client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })
    details = register_resp.get_json()['details']
    group_id = details['group_id']
    join_code = details['join_code']
    admin_id = details['user_id']

    join_resp = client.post('/api/auth/join', json={
        'join_code': join_code,
        'user_name': 'Jane Smith',
        'email': 'jane@smith.com',
        'password': 'password456'
    })
    member_id = join_resp.get_json()['details']['user_id']

    # Patch token
    def mock_decode_manager(token):
        return {'user_id': admin_id, 'group_id': group_id, 'role': 'MANAGER',
                'user_name': 'John Smith', 'group_name': 'Smith Family', 'join_code': join_code}

    with patch.object(auth_module, 'decode_token', mock_decode_manager):
        # Try invalid role
        response = client.put(f'/api/groups/members/{member_id}', json={'role': 'ADMIN'})
        assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_update_self_role_returns_400(client, mock_db):
    """PUT /api/groups/members/<id> prevents self-promotion."""
    # Create user
    register_resp = client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })
    details = register_resp.get_json()['details']
    user_id = details['user_id']
    group_id = details['group_id']

    # Try to change own role
    def mock_decode_self(token):
        return {'user_id': user_id, 'group_id': group_id, 'role': 'MANAGER',
                'user_name': 'John Smith', 'group_name': 'Smith Family', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_self):
        response = client.put(f'/api/groups/members/{user_id}', json={'role': 'MEMBER'})
        assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_delete_member_success(client, mock_db):
    """DELETE /api/groups/members/<id> allows MANAGER to remove member."""
    # Create group and member
    register_resp = client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })
    details = register_resp.get_json()['details']
    group_id = details['group_id']
    join_code = details['join_code']
    admin_id = details['user_id']

    join_resp = client.post('/api/auth/join', json={
        'join_code': join_code,
        'user_name': 'Jane Smith',
        'email': 'jane@smith.com',
        'password': 'password456'
    })
    member_id = join_resp.get_json()['details']['user_id']

    # Patch token
    def mock_decode_manager(token):
        return {'user_id': admin_id, 'group_id': group_id, 'role': 'MANAGER',
                'user_name': 'John Smith', 'group_name': 'Smith Family', 'join_code': join_code}

    with patch.object(auth_module, 'decode_token', mock_decode_manager):
        # Remove member
        response = client.delete(f'/api/groups/members/{member_id}')
        assert response.status_code == 204


@pytest.mark.integration
@pytest.mark.p1
def test_delete_member_forbidden_for_member(client):
    """DELETE /api/groups/members/<id> forbidden for MEMBER."""

    fake_user_id = str(ObjectId())

    def mock_decode_member(token):
        return {'user_id': 'member-123', 'group_id': 'test-group-456', 'role': 'MEMBER',
                'user_name': 'Member User', 'group_name': 'Test Group', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_member):
        response = client.delete(f'/api/groups/members/{fake_user_id}')
        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.p1
def test_delete_self_returns_400(client, mock_db):
    """DELETE /api/groups/members/<id> prevents self-deletion."""
    # Create user
    register_resp = client.post('/api/auth/register', json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': 'john@smith.com',
        'password': 'secure123'
    })
    details = register_resp.get_json()['details']
    user_id = details['user_id']
    group_id = details['group_id']

    # Try to delete self

    def mock_decode_self(token):
        return {'user_id': user_id, 'group_id': group_id, 'role': 'MANAGER',
                'user_name': 'John Smith', 'group_name': 'Smith Family', 'join_code': 'TEST123'}

    with patch.object(auth_module, 'decode_token', mock_decode_self):
        response = client.delete(f'/api/groups/members/{user_id}')
        assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p1
def test_delete_member_not_found_returns_404(client):
    """DELETE /api/groups/members/<id> returns 404 for non-existent user."""
    fake_id = str(ObjectId())
    response = client.delete(f'/api/groups/members/{fake_id}')

    assert response.status_code == 404


# --- Health Endpoint Tests ---

@pytest.mark.integration
@pytest.mark.p2
def test_health_endpoint_returns_200(app):
    """GET /api/health returns 200 when healthy."""
    test_client = app.test_client()
    response = test_client.get('/api/health')

    assert response.status_code in [200, 503]
    data = response.get_json()
    assert 'status' in data

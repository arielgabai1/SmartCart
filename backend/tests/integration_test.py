"""
Integration tests - API endpoints with mocked database.
Covers all API routes, authentication, authorization, and multi-tenancy.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
from bson import ObjectId
from unittest.mock import patch
import auth as auth_module


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
    """GET /health returns 200 when healthy."""
    test_client = app.test_client()
    response = test_client.get('/health')

    assert response.status_code in [200, 503]
    data = response.get_json()
    assert 'status' in data

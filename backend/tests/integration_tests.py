"""
Integration Tests - Test real API endpoints against actual docker-compose stack.
No mocking - tests hit real MongoDB, real Flask app, real services.
"""
import pytest
import requests
import uuid
import os

# Base URL for API calls - defaults to frontend for CI, override with TEST_BASE_URL for local
BASE_URL = os.getenv('TEST_BASE_URL', 'http://frontend/api')

def unique_email():
    """Generate unique email for testing."""
    return f"test-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def registered_group():
    """Register a test group and return credentials with token."""
    email = unique_email()
    password = 'password123'

    # Register
    register_response = requests.post(f"{BASE_URL}/auth/register", json={
        'group_name': 'Test Family',
        'user_name': 'Admin User',
        'email': email,
        'password': password
    })
    assert register_response.status_code == 201, f"Register failed: {register_response.text}"
    register_data = register_response.json()

    # Login to get token
    login_response = requests.post(f"{BASE_URL}/auth/login", json={
        'email': email,
        'password': password
    })
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    login_data = login_response.json()

    return {
        'token': login_data['token'],
        'user_id': register_data['details']['user_id'],
        'group_id': register_data['details']['group_id'],
        'join_code': register_data['details']['join_code'],
        'email': email,
        'password': password
    }


@pytest.fixture
def member_in_group(registered_group):
    """Add a member to the test group."""
    email = unique_email()
    password = 'password123'

    # Join group
    join_response = requests.post(f"{BASE_URL}/auth/join", json={
        'join_code': registered_group['join_code'],
        'user_name': 'Member User',
        'email': email,
        'password': password
    })
    assert join_response.status_code == 201, f"Join failed: {join_response.text}"
    join_data = join_response.json()

    # Login to get token
    login_response = requests.post(f"{BASE_URL}/auth/login", json={
        'email': email,
        'password': password
    })
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    login_data = login_response.json()

    return {
        'token': login_data['token'],
        'user_id': join_data['details']['user_id'],
        'group_id': join_data['details']['group_id'],
        'email': email,
        'password': password
    }


# --- Health Check ---

@pytest.mark.integration
def test_health_endpoint():
    """GET /api/health returns healthy status."""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json()['status'] == 'healthy'


# --- Auth API Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_register_group_success():
    """POST /api/auth/register creates group and admin user."""
    response = requests.post(f"{BASE_URL}/auth/register", json={
        'group_name': 'Smith Family',
        'user_name': 'John Smith',
        'email': unique_email(),
        'password': 'secure123'
    })
    assert response.status_code == 201
    data = response.json()
    assert data['message'] == 'Group created!'
    assert data['details']['role'] == 'MANAGER'
    assert 'group_id' in data['details']
    assert 'join_code' in data['details']


@pytest.mark.integration
@pytest.mark.p1
def test_register_duplicate_email(registered_group):
    """POST /api/auth/register rejects duplicate email."""
    response = requests.post(f"{BASE_URL}/auth/register", json={
        'group_name': 'Another Family',
        'user_name': 'John',
        'email': registered_group['email'],  # Use same email as registered group
        'password': 'pass'
    })
    assert response.status_code == 400
    assert 'email already exists' in response.json()['details'][0].lower()


@pytest.mark.integration
@pytest.mark.p1
def test_register_missing_fields():
    """POST /api/auth/register rejects missing fields."""
    response = requests.post(f"{BASE_URL}/auth/register", json={'group_name': 'Incomplete'})
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_join_group_success(registered_group):
    """POST /api/auth/join allows member to join via join code."""
    response = requests.post(f"{BASE_URL}/auth/join", json={
        'join_code': registered_group['join_code'],
        'user_name': 'Jane Doe',
        'email': 'jane@test.com',
        'password': 'pass456'
    })
    assert response.status_code == 201
    data = response.json()
    assert data['details']['role'] == 'MEMBER'
    assert data['details']['group_id'] == registered_group['group_id']


@pytest.mark.integration
@pytest.mark.p1
def test_join_invalid_code():
    """POST /api/auth/join rejects invalid join code."""
    response = requests.post(f"{BASE_URL}/auth/join", json={
        'join_code': 'INVALID',
        'user_name': 'Jane',
        'email': 'jane@test.com',
        'password': 'pass'
    })
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_login_success(registered_group):
    """POST /api/auth/login returns token for valid credentials."""
    response = requests.post(f"{BASE_URL}/auth/login", json={
        'email': registered_group['email'],
        'password': registered_group['password']
    })
    assert response.status_code == 200
    assert 'token' in response.json()


@pytest.mark.integration
@pytest.mark.p1
def test_login_invalid_credentials(registered_group):
    """POST /api/auth/login rejects invalid credentials."""
    response = requests.post(f"{BASE_URL}/auth/login", json={
        'email': registered_group['email'],
        'password': 'wrongpassword'
    })
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.p0
def test_get_current_user(registered_group):
    """GET /api/auth/me returns current user info."""
    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers={'Authorization': f"Bearer {registered_group['token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data['user_id'] == registered_group['user_id']
    assert data['role'] == 'MANAGER'


@pytest.mark.integration
@pytest.mark.p1
def test_get_current_user_no_token():
    """GET /api/auth/me returns 401 without token."""
    response = requests.get(f"{BASE_URL}/auth/me")
    assert response.status_code == 401


# --- Items API Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_get_items_empty(registered_group):
    """GET /api/items returns empty list initially."""
    response = requests.get(
        f"{BASE_URL}/items",
        headers={'Authorization': f"Bearer {registered_group['token']}"}
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
@pytest.mark.p0
def test_post_item_success_manager(registered_group):
    """POST /api/items creates item with APPROVED status for MANAGER."""
    response = requests.post(
        f"{BASE_URL}/items",
        headers={'Authorization': f"Bearer {registered_group['token']}"},
        json={'name': 'Milk', 'category': 'Dairy'}
    )
    assert response.status_code == 201
    data = response.json()
    assert data['name'] == 'Milk'
    assert data['status'] == 'APPROVED'
    assert data['ai_status'] == 'CALCULATING'


@pytest.mark.integration
@pytest.mark.p0
def test_post_item_success_member(member_in_group):
    """POST /api/items creates item with PENDING status for MEMBER."""
    response = requests.post(
        f"{BASE_URL}/items",
        headers={'Authorization': f"Bearer {member_in_group['token']}"},
        json={'name': 'Bread'}
    )
    assert response.status_code == 201
    data = response.json()
    assert data['name'] == 'Bread'
    assert data['status'] == 'PENDING'


@pytest.mark.integration
@pytest.mark.p1
def test_post_item_missing_name(registered_group):
    """POST /api/items with missing name returns 400."""
    response = requests.post(
        f"{BASE_URL}/items",
        headers={'Authorization': f"Bearer {registered_group['token']}"},
        json={}
    )
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.p0
def test_get_items_returns_created(registered_group):
    """GET /api/items returns created items."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}

    requests.post(f"{BASE_URL}/items", headers=headers, json={'name': 'Eggs'})
    requests.post(f"{BASE_URL}/items", headers=headers, json={'name': 'Bread'})

    response = requests.get(f"{BASE_URL}/items", headers=headers)
    data = response.json()
    assert len(data) == 2
    assert set(i['name'] for i in data) == {'Eggs', 'Bread'}


@pytest.mark.integration
@pytest.mark.p0
def test_put_item_updates_status(registered_group):
    """PUT /api/items/<id> updates status (MANAGER only)."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}

    # Create item
    create_resp = requests.post(f"{BASE_URL}/items", headers=headers, json={'name': 'Candy'})
    item_id = create_resp.json()['_id']

    # Update status
    response = requests.put(
        f"{BASE_URL}/items/{item_id}",
        headers=headers,
        json={'status': 'REJECTED'}
    )
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.p1
def test_member_cannot_update_status(registered_group, member_in_group):
    """MEMBER cannot update item status."""
    manager_headers = {'Authorization': f"Bearer {registered_group['token']}"}
    member_headers = {'Authorization': f"Bearer {member_in_group['token']}"}

    # Manager creates item
    create_resp = requests.post(f"{BASE_URL}/items", headers=manager_headers, json={'name': 'Item'})
    item_id = create_resp.json()['_id']

    # Member tries to update status
    response = requests.put(
        f"{BASE_URL}/items/{item_id}",
        headers=member_headers,
        json={'status': 'APPROVED'}
    )
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.p0
def test_put_item_updates_quantity(registered_group):
    """PUT /api/items/<id> allows MANAGER to update quantity."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}

    create_resp = requests.post(f"{BASE_URL}/items", headers=headers, json={'name': 'Candy'})
    item_id = create_resp.json()['_id']

    response = requests.put(f"{BASE_URL}/items/{item_id}", headers=headers, json={'quantity': 5})
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.p0
def test_delete_item_by_manager(registered_group):
    """DELETE /api/items/<id> allows MANAGER to delete any item."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}

    create_resp = requests.post(f"{BASE_URL}/items", headers=headers, json={'name': 'Juice'})
    item_id = create_resp.json()['_id']

    response = requests.delete(f"{BASE_URL}/items/{item_id}", headers=headers)
    assert response.status_code == 204

    # Verify deletion
    items = requests.get(f"{BASE_URL}/items", headers=headers).json()
    assert len(items) == 0


@pytest.mark.integration
@pytest.mark.p1
def test_delete_item_by_owner(member_in_group):
    """DELETE /api/items/<id> allows owner to delete their own item."""
    headers = {'Authorization': f"Bearer {member_in_group['token']}"}

    create_resp = requests.post(f"{BASE_URL}/items", headers=headers, json={'name': 'Snack'})
    item_id = create_resp.json()['_id']

    response = requests.delete(f"{BASE_URL}/items/{item_id}", headers=headers)
    assert response.status_code == 204


@pytest.mark.integration
@pytest.mark.p1
def test_delete_item_not_found(registered_group):
    """DELETE /api/items/<id> returns 404 for non-existent item."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}
    response = requests.delete(f"{BASE_URL}/items/507f1f77bcf86cd799439011", headers=headers)
    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.p0
def test_delete_all_items(registered_group):
    """DELETE /api/items/clear allows MANAGER to clear all items."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}

    for name in ['Item1', 'Item2', 'Item3']:
        requests.post(f"{BASE_URL}/items", headers=headers, json={'name': name})

    response = requests.delete(f"{BASE_URL}/items/clear", headers=headers)
    assert response.status_code == 204

    items = requests.get(f"{BASE_URL}/items", headers=headers).json()
    assert len(items) == 0


@pytest.mark.integration
@pytest.mark.p1
def test_delete_all_forbidden_for_member(member_in_group):
    """DELETE /api/items/clear forbidden for MEMBER."""
    headers = {'Authorization': f"Bearer {member_in_group['token']}"}
    response = requests.delete(f"{BASE_URL}/items/clear", headers=headers)
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.p0
def test_crud_flow_complete(registered_group):
    """Test complete CRUD flow for items."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}

    # Create
    create_resp = requests.post(f"{BASE_URL}/items", headers=headers, json={'name': 'Coffee'})
    item_id = create_resp.json()['_id']

    # Read
    items = requests.get(f"{BASE_URL}/items", headers=headers).json()
    assert len(items) == 1

    # Update
    update_resp = requests.put(f"{BASE_URL}/items/{item_id}", headers=headers, json={'quantity': 3})
    assert update_resp.status_code == 200

    # Delete
    delete_resp = requests.delete(f"{BASE_URL}/items/{item_id}", headers=headers)
    assert delete_resp.status_code == 204

    # Verify deletion
    items = requests.get(f"{BASE_URL}/items", headers=headers).json()
    assert len(items) == 0


# --- Multi-Tenancy Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_multi_tenancy_isolation():
    """Items are isolated by group_id."""
    # Register and login first group
    email_a = unique_email()
    password_a = 'pass123'
    requests.post(f"{BASE_URL}/auth/register", json={
        'group_name': 'Group A',
        'user_name': 'User A',
        'email': email_a,
        'password': password_a
    })
    token_a = requests.post(f"{BASE_URL}/auth/login", json={
        'email': email_a,
        'password': password_a
    }).json()['token']

    # Register and login second group
    email_b = unique_email()
    password_b = 'pass123'
    requests.post(f"{BASE_URL}/auth/register", json={
        'group_name': 'Group B',
        'user_name': 'User B',
        'email': email_b,
        'password': password_b
    })
    token_b = requests.post(f"{BASE_URL}/auth/login", json={
        'email': email_b,
        'password': password_b
    }).json()['token']

    headers_a = {'Authorization': f"Bearer {token_a}"}
    headers_b = {'Authorization': f"Bearer {token_b}"}

    # Group A creates item
    requests.post(f"{BASE_URL}/items", headers=headers_a, json={'name': 'Group A Item'})

    # Group B creates item
    requests.post(f"{BASE_URL}/items", headers=headers_b, json={'name': 'Group B Item'})

    # Each group sees only their items
    items_a = requests.get(f"{BASE_URL}/items", headers=headers_a).json()
    items_b = requests.get(f"{BASE_URL}/items", headers=headers_b).json()

    assert len(items_a) == 1
    assert len(items_b) == 1
    assert items_a[0]['name'] == 'Group A Item'
    assert items_b[0]['name'] == 'Group B Item'


# --- Group Management API Tests ---

@pytest.mark.integration
@pytest.mark.p0
def test_get_group_members(registered_group, member_in_group):
    """GET /api/groups/members returns member list."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}
    response = requests.get(f"{BASE_URL}/groups/members", headers=headers)
    assert response.status_code == 200
    members = response.json()
    assert len(members) == 2  # Admin + member


@pytest.mark.integration
@pytest.mark.p0
def test_update_member_role(registered_group, member_in_group):
    """PUT /api/groups/members/<id> allows MANAGER to update role."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}
    response = requests.put(
        f"{BASE_URL}/groups/members/{member_in_group['user_id']}",
        headers=headers,
        json={'role': 'MANAGER'}
    )
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.p1
def test_update_member_role_forbidden_for_member(registered_group, member_in_group):
    """PUT /api/groups/members/<id> forbidden for MEMBER."""
    member_headers = {'Authorization': f"Bearer {member_in_group['token']}"}
    response = requests.put(
        f"{BASE_URL}/groups/members/{registered_group['user_id']}",
        headers=member_headers,
        json={'role': 'MEMBER'}
    )
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.p0
def test_delete_member(registered_group, member_in_group):
    """DELETE /api/groups/members/<id> allows MANAGER to remove member."""
    headers = {'Authorization': f"Bearer {registered_group['token']}"}
    response = requests.delete(
        f"{BASE_URL}/groups/members/{member_in_group['user_id']}",
        headers=headers
    )
    assert response.status_code == 204


@pytest.mark.integration
@pytest.mark.p1
def test_delete_member_forbidden_for_member(registered_group, member_in_group):
    """DELETE /api/groups/members/<id> forbidden for MEMBER."""
    member_headers = {'Authorization': f"Bearer {member_in_group['token']}"}
    response = requests.delete(
        f"{BASE_URL}/groups/members/{registered_group['user_id']}",
        headers=member_headers
    )
    assert response.status_code == 403

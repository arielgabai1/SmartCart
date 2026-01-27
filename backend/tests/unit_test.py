"""
Unit tests - Isolated business logic with mocked dependencies.
Covers all validation functions, utilities, and helper methods.
"""
import sys
sys.path.insert(0, '/app/src')

import pytest
from bson import ObjectId
from datetime import datetime, timezone
import re


# --- Item Validation Tests ---

@pytest.mark.unit
def test_validate_item_success():
    """validate_item accepts valid item data with all fields."""
    from models import validate_item

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
    from models import validate_item

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
    from models import validate_item

    data = {'group_id': 'test-group-123'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('name' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_empty_name():
    """validate_item rejects empty or whitespace-only name."""
    from models import validate_item

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
    from models import validate_item

    data = {'name': 'Bread'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('group_id' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_strips_whitespace():
    """validate_item strips whitespace from name and category."""
    from models import validate_item

    data = {'name': '  Eggs  ', 'group_id': 'test-group-123', 'category': '  Protein  '}
    validated, errors = validate_item(data)

    assert errors == []
    assert validated['name'] == 'Eggs'
    assert validated['category'] == 'Protein'


@pytest.mark.unit
def test_validate_item_invalid_status():
    """validate_item rejects invalid status."""
    from models import validate_item

    data = {'name': 'Candy', 'group_id': 'test-group-123', 'status': 'INVALID'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('status' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_invalid_quantity():
    """validate_item rejects invalid or negative quantity."""
    from models import validate_item

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
    from models import validate_item

    data = {'name': 'Candy', 'group_id': 'test-group-123', 'price_nis': 'expensive'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('price_nis' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_invalid_ai_status():
    """validate_item rejects invalid ai_status."""
    from models import validate_item

    data = {'name': 'Candy', 'group_id': 'test-group-123', 'ai_status': 'INVALID'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('ai_status' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_item_invalid_user_role():
    """validate_item rejects invalid user_role."""
    from models import validate_item

    data = {'name': 'Candy', 'group_id': 'test-group-123', 'user_role': 'ADMIN'}
    validated, errors = validate_item(data)

    assert len(errors) > 0
    assert any('user_role' in err.lower() for err in errors)


# --- User Validation Tests ---

@pytest.mark.unit
def test_validate_user_success():
    """validate_user accepts valid user data."""
    from models import validate_user

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
    from models import validate_user

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
    from models import validate_user

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
    from models import validate_user

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
    from models import validate_user

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
    from models import validate_group

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
    from models import validate_group

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
    from models import validate_group

    data = {}
    validated, errors = validate_group(data)

    assert len(errors) > 0
    assert any('name' in err.lower() for err in errors)


@pytest.mark.unit
def test_validate_group_empty_name():
    """validate_group rejects empty or whitespace-only name."""
    from models import validate_group

    data = {'name': '   '}
    validated, errors = validate_group(data)

    assert len(errors) > 0
    assert any('name' in err.lower() for err in errors)


# --- Helper Function Tests ---

@pytest.mark.unit
def test_item_to_dict_converts_objectid():
    """item_to_dict converts MongoDB ObjectId to string."""
    from models import item_to_dict

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
    from models import item_to_dict

    item = {'_id': ObjectId(), 'name': 'Test'}
    result = item_to_dict(item)

    assert result['ai_status'] is None
    assert result['ai_latency'] is None
    assert result['quantity'] == 1
    assert result['submitted_by_name'] == 'Group Member'


@pytest.mark.unit
def test_item_to_dict_preserves_submitted_by_name():
    """item_to_dict preserves submitted_by_name if present."""
    from models import item_to_dict

    item = {'_id': ObjectId(), 'name': 'Test', 'submitted_by_name': 'Alice'}
    result = item_to_dict(item)

    assert result['submitted_by_name'] == 'Alice'


@pytest.mark.unit
def test_user_to_dict_removes_password():
    """user_to_dict removes password_hash from user data."""
    from models import user_to_dict

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
    from auth import hash_password

    password = 'my_secure_password'
    hashed = hash_password(password)

    assert isinstance(hashed, str)
    assert len(hashed) > 0
    assert hashed != password
    assert hashed.startswith('$2b$')  # bcrypt hash prefix


@pytest.mark.unit
def test_verify_password_success():
    """verify_password returns True for correct password."""
    from auth import hash_password, verify_password

    password = 'correct_password'
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


@pytest.mark.unit
def test_verify_password_failure():
    """verify_password returns False for incorrect password."""
    from auth import hash_password, verify_password

    password = 'correct_password'
    hashed = hash_password(password)

    assert verify_password('wrong_password', hashed) is False


@pytest.mark.unit
def test_generate_token():
    """generate_token creates a valid JWT with all claims."""
    from auth import generate_token, decode_token

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
    from auth import decode_token

    assert decode_token('invalid.token.here') is None
    assert decode_token('') is None


# --- AI Engine Tests ---

@pytest.mark.unit
def test_ai_engine_fallback_no_api_key(monkeypatch):
    """estimate_item_price returns fallback when OPENAI_API_KEY not set."""
    from ai_engine import estimate_item_price

    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    price, status = estimate_item_price('Milk', 'Dairy')

    assert price == 0.0  # Fallback price
    assert status == 'ERROR'


@pytest.mark.unit
def test_ai_engine_fallback_empty_api_key(monkeypatch):
    """estimate_item_price returns fallback when OPENAI_API_KEY is empty."""
    from ai_engine import estimate_item_price

    monkeypatch.setenv('OPENAI_API_KEY', '')
    price, status = estimate_item_price('Bread', 'Bakery')

    assert price == 0.0
    assert status == 'ERROR'

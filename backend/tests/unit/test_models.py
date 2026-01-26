"""
Unit tests for Item schema validation (models.py).

Tests validate_item function ensuring schema enforcement and multi-tenancy support.
"""
import pytest
from datetime import datetime
from src.models import (
    validate_item,
    item_to_dict,
    VALID_USER_ROLES,
    VALID_STATUSES,
    DEFAULT_STATUS,
    DEFAULT_PRICE_NIS,
    MAX_ITEM_NAME_LENGTH
)


class TestValidateItem:
    """Test suite for validate_item function."""

    def test_valid_item_creation_minimal(self):
        """Test valid item with minimal required fields."""
        data = {
            'family_id': 'test-family-123',
            'name': 'Apple'
        }
        validated, errors = validate_item(data)

        assert errors == []
        assert validated['family_id'] == 'test-family-123'
        assert validated['name'] == 'Apple'
        assert validated['status'] == DEFAULT_STATUS
        assert validated['price_nis'] == DEFAULT_PRICE_NIS
        assert 'created_at' in validated
        assert isinstance(validated['created_at'], datetime)

    def test_valid_item_creation_full(self):
        """Test valid item with all fields provided."""
        data = {
            'family_id': 'family-456',
            'name': 'Banana',
            'user_role': 'KID',
            'status': 'APPROVED',
            'price_nis': 15.5
        }
        validated, errors = validate_item(data)

        assert errors == []
        assert validated['family_id'] == 'family-456'
        assert validated['name'] == 'Banana'
        assert validated['user_role'] == 'KID'
        assert validated['status'] == 'APPROVED'
        assert validated['price_nis'] == 15.5
        assert 'created_at' in validated

    def test_missing_family_id(self):
        """Test that missing family_id causes validation error."""
        data = {'name': 'Orange'}
        validated, errors = validate_item(data)

        assert len(errors) > 0
        assert any('family_id' in err.lower() for err in errors)

    def test_empty_family_id(self):
        """Test that empty family_id causes validation error."""
        data = {'family_id': '', 'name': 'Grape'}
        validated, errors = validate_item(data)

        assert len(errors) > 0
        assert any('family_id' in err.lower() for err in errors)

    def test_missing_name(self):
        """Test that missing name causes validation error."""
        data = {'family_id': 'family-789'}
        validated, errors = validate_item(data)

        assert len(errors) > 0
        assert any('name' in err.lower() for err in errors)

    def test_empty_name(self):
        """Test that empty name causes validation error."""
        data = {'family_id': 'family-101', 'name': ''}
        validated, errors = validate_item(data)

        assert len(errors) > 0
        assert any('name' in err.lower() for err in errors)

    def test_whitespace_only_name(self):
        """Test that whitespace-only name causes validation error."""
        data = {'family_id': 'family-102', 'name': '   '}
        validated, errors = validate_item(data)

        assert len(errors) > 0
        assert any('name' in err.lower() for err in errors)

    def test_name_too_long(self):
        """Test that name exceeding max length causes validation error."""
        long_name = 'A' * (MAX_ITEM_NAME_LENGTH + 1)
        data = {'family_id': 'family-103', 'name': long_name}
        validated, errors = validate_item(data)

        assert len(errors) > 0
        assert any('name' in err.lower() and str(MAX_ITEM_NAME_LENGTH) in err for err in errors)

    def test_invalid_user_role(self):
        """Test that invalid user_role causes validation error."""
        data = {
            'family_id': 'family-104',
            'name': 'Mango',
            'user_role': 'INVALID_ROLE'
        }
        validated, errors = validate_item(data)

        assert len(errors) > 0
        assert any('user_role' in err.lower() for err in errors)

    @pytest.mark.parametrize('valid_role', VALID_USER_ROLES)
    def test_valid_user_roles(self, valid_role):
        """Test that all valid user roles are accepted."""
        data = {
            'family_id': 'family-105',
            'name': 'Peach',
            'user_role': valid_role
        }
        validated, errors = validate_item(data)

        assert errors == []
        assert validated['user_role'] == valid_role

    def test_invalid_status(self):
        """Test that invalid status causes validation error."""
        data = {
            'family_id': 'family-106',
            'name': 'Pear',
            'status': 'INVALID_STATUS'
        }
        validated, errors = validate_item(data)

        assert len(errors) > 0
        assert any('status' in err.lower() for err in errors)

    @pytest.mark.parametrize('valid_status', VALID_STATUSES)
    def test_valid_statuses(self, valid_status):
        """Test that all valid statuses are accepted."""
        data = {
            'family_id': 'family-107',
            'name': 'Plum',
            'status': valid_status
        }
        validated, errors = validate_item(data)

        assert errors == []
        assert validated['status'] == valid_status

    def test_invalid_price_nis_non_numeric(self):
        """Test that non-numeric price_nis causes validation error."""
        data = {
            'family_id': 'family-108',
            'name': 'Cherry',
            'price_nis': 'not_a_number'
        }
        validated, errors = validate_item(data)

        assert len(errors) > 0
        assert any('price_nis' in err.lower() for err in errors)

    def test_price_nis_string_numeric(self):
        """Test that numeric string price_nis is converted to float."""
        data = {
            'family_id': 'family-109',
            'name': 'Kiwi',
            'price_nis': '12.50'
        }
        validated, errors = validate_item(data)

        assert errors == []
        assert validated['price_nis'] == 12.50
        assert isinstance(validated['price_nis'], float)

    def test_name_whitespace_trimming(self):
        """Test that name whitespace is trimmed."""
        data = {
            'family_id': 'family-110',
            'name': '  Watermelon  '
        }
        validated, errors = validate_item(data)

        assert errors == []
        assert validated['name'] == 'Watermelon'

    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are collected."""
        data = {
            'name': '',
            'user_role': 'INVALID',
            'status': 'INVALID',
            'price_nis': 'invalid'
        }
        validated, errors = validate_item(data)

        # Should have errors for: family_id, name, user_role, status, price_nis
        assert len(errors) >= 4


class TestItemToDict:
    """Test suite for item_to_dict function."""

    def test_converts_object_id_to_string(self):
        """Test that _id is converted to string."""
        from bson import ObjectId
        item = {
            '_id': ObjectId('507f1f77bcf86cd799439011'),
            'name': 'Test Item',
            'price_nis': 10.0
        }
        result = item_to_dict(item)

        assert isinstance(result['_id'], str)
        assert result['_id'] == '507f1f77bcf86cd799439011'
        assert result['name'] == 'Test Item'

    def test_handles_item_without_id(self):
        """Test that items without _id are handled gracefully."""
        item = {
            'name': 'Test Item',
            'price_nis': 10.0
        }
        result = item_to_dict(item)

        assert '_id' not in result
        assert result['name'] == 'Test Item'

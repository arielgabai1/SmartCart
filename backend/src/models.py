"""
Data models and validation logic for Smart Cart.

Provides schema validation for Items with multi-tenancy support via family_id.
"""
from datetime import datetime
from typing import Dict, Any, List, Tuple


# Constants for validation
VALID_USER_ROLES = ['PARENT', 'KID']
VALID_STATUSES = ['PENDING', 'APPROVED', 'REJECTED', 'ERROR']
MAX_ITEM_NAME_LENGTH = 200
DEFAULT_STATUS = 'PENDING'
DEFAULT_PRICE_NIS = 0.0


class ValidationError(Exception):
    """Raised when item validation fails."""
    pass


def validate_item(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate and prepare item data for insertion.

    Args:
        data: Raw item data dictionary

    Returns:
        Tuple of (validated_item_dict, list_of_errors)
        If errors list is not empty, validation failed.

    Validation Rules:
        - family_id: Required (UUID string)
        - name: Required, non-empty, max 200 chars
        - user_role: Optional, must be PARENT or KID if provided
        - status: Optional, defaults to PENDING
        - price_nis: Optional, defaults to 0.0
        - created_at: Auto-generated if not provided
    """
    errors = []
    validated = {}

    # Required: family_id
    if 'family_id' not in data or not data.get('family_id'):
        errors.append('family_id is required for multi-tenancy')
    else:
        validated['family_id'] = data['family_id']

    # Required: name
    if 'name' not in data:
        errors.append('name is required')
    elif not data['name'] or not str(data['name']).strip():
        errors.append('name cannot be empty or whitespace')
    elif len(str(data['name'])) > MAX_ITEM_NAME_LENGTH:
        errors.append(f'name cannot exceed {MAX_ITEM_NAME_LENGTH} characters')
    else:
        validated['name'] = str(data['name']).strip()

    # Optional: user_role (with validation)
    if 'user_role' in data:
        if data['user_role'] not in VALID_USER_ROLES:
            errors.append(f'user_role must be one of: {", ".join(VALID_USER_ROLES)}')
        else:
            validated['user_role'] = data['user_role']

    # Optional: status (with validation and default)
    if 'status' in data:
        if data['status'] not in VALID_STATUSES:
            errors.append(f'status must be one of: {", ".join(VALID_STATUSES)}')
        else:
            validated['status'] = data['status']
    else:
        validated['status'] = DEFAULT_STATUS

    # Optional: price_nis (with default)
    if 'price_nis' in data:
        try:
            validated['price_nis'] = float(data['price_nis'])
        except (ValueError, TypeError):
            errors.append('price_nis must be a valid number')
    else:
        validated['price_nis'] = DEFAULT_PRICE_NIS

    # Auto-generate created_at if not provided
    if 'created_at' not in data:
        validated['created_at'] = datetime.utcnow()
    else:
        validated['created_at'] = data['created_at']

    return validated, errors


def item_to_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert MongoDB item document to API-safe dictionary.

    Converts ObjectId to string for JSON serialization.

    Args:
        item: MongoDB document

    Returns:
        Dictionary safe for JSON serialization
    """
    if '_id' in item:
        item['_id'] = str(item['_id'])
    return item

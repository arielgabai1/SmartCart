"""
Data models and validation logic for Smart Cart.

Provides schema validation for Items, Users, and Groups with multi-tenancy support.
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
import re
import random
import string

# Constants for validation
VALID_USER_ROLES = {'MANAGER', 'MEMBER'}
VALID_STATUSES = {'PENDING', 'APPROVED', 'REJECTED', 'ERROR'}
VALID_AI_STATUSES = {'CALCULATING', 'COMPLETED', 'ERROR'}
MAX_ITEM_NAME_LENGTH = 200
DEFAULT_STATUS = 'PENDING'
DEFAULT_PRICE_NIS = 0.0

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

class ValidationError(Exception):
    """Raised when item validation fails."""
    pass

# --- Helpers ---

def _validate_required(data: Dict[str, Any], field: str, error_msg: str, errors: List[str]) -> None:
    """Helper to validate required fields."""
    if field not in data or not data[field]:
        errors.append(error_msg)

def _validate_string(value: Any, max_len: Optional[int] = None) -> Optional[str]:
    """Helper to validate and strip strings."""
    if not value:
        return None
    val = str(value).strip()
    if not val:
        return None
    if max_len and len(val) > max_len:
        return None # Or raise error
    return val

# --- Item Validation ---

def validate_item(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and prepare item data for insertion."""
    errors = []
    validated = {}

    # Required: group_id
    if not data.get('group_id'):
        errors.append('group_id is required for multi-tenancy')
    else:
        validated['group_id'] = str(data['group_id'])

    # Required: name
    if 'name' not in data:
        errors.append('name is required')
    elif not data['name'] or not str(data['name']).strip():
        errors.append('name cannot be empty or whitespace')
    elif len(str(data['name'])) > MAX_ITEM_NAME_LENGTH:
        errors.append(f'name cannot exceed {MAX_ITEM_NAME_LENGTH} characters')
    else:
        validated['name'] = str(data['name']).strip()

    # Optional Fields with Defaults
    validated['category'] = _validate_string(data.get('category')) or 'OTHER'
    validated['submitted_by'] = _validate_string(data.get('submitted_by')) or 'Anonymous'
    validated['submitted_by_name'] = _validate_string(data.get('submitted_by_name')) or 'Group Member'

    # Enum Validations
    if 'user_role' in data:
        if data['user_role'] not in VALID_USER_ROLES:
            errors.append(f'user_role must be one of: {", ".join(VALID_USER_ROLES)}')
        else:
            validated['user_role'] = data['user_role']

    # Status
    status = data.get('status', DEFAULT_STATUS)
    if status not in VALID_STATUSES:
        errors.append(f'status must be one of: {", ".join(VALID_STATUSES)}')
    else:
        validated['status'] = status

    # Numeric Fields
    try:
        validated['price_nis'] = float(data.get('price_nis', DEFAULT_PRICE_NIS))
    except (ValueError, TypeError):
        errors.append('price_nis must be a valid number')

    try:
        qty = int(data.get('quantity', 1))
        if qty < 1:
            errors.append('quantity must be at least 1')
        else:
            validated['quantity'] = qty
    except (ValueError, TypeError):
        errors.append('quantity must be a valid integer')

    # AI Fields
    if 'ai_status' in data:
        if data['ai_status'] not in VALID_AI_STATUSES:
             errors.append(f'ai_status must be one of: {", ".join(VALID_AI_STATUSES)}')
        else:
            validated['ai_status'] = data['ai_status']

    if 'ai_latency' in data and data['ai_latency'] is not None:
        try:
            validated['ai_latency'] = float(data['ai_latency'])
        except (ValueError, TypeError):
            errors.append('ai_latency must be a valid number')
    else:
        validated['ai_latency'] = None

    validated['created_at'] = data.get('created_at', datetime.now(timezone.utc))

    return validated, errors

# --- User Validation ---

def validate_user(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and prepare user data for insertion."""
    errors = []
    validated = {}

    # Email
    email = str(data.get('email', '')).lower().strip()
    if not re.match(EMAIL_REGEX, email):
        errors.append('A valid email address is required')
    else:
        validated['email'] = email

    # Password Hash
    if 'password_hash' not in data:
        errors.append('password_hash is required')
    else:
        validated['password_hash'] = data['password_hash']

    # Group ID
    if 'group_id' not in data:
        errors.append('group_id is required')
    else:
        validated['group_id'] = str(data['group_id'])

    # Role
    if data.get('role') not in VALID_USER_ROLES:
        errors.append(f'role must be one of: {", ".join(VALID_USER_ROLES)}')
    else:
        validated['role'] = data['role']

    validated['full_name'] = str(data.get('full_name', '')).strip()
    validated['created_at'] = datetime.now(timezone.utc)

    return validated, errors

# --- Group Validation ---

def validate_group(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and prepare group data for insertion."""
    errors = []
    validated = {}

    # Name
    name = _validate_string(data.get('name'))
    if not name:
        errors.append('group name is required')
    else:
        validated['name'] = name

    # Join Code (Generate if missing)
    validated['join_code'] = data.get('join_code', 
        ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)))

    validated['created_at'] = datetime.now(timezone.utc)
    validated['subscription_tier'] = data.get('subscription_tier', 'FREE')

    return validated, errors

# --- Serialization Helpers ---

def item_to_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB item document to API-safe dictionary."""
    if '_id' in item:
        item['_id'] = str(item['_id'])
    
    # Priority: 1. Human Name, 2. Submission Label, 3. 'Group Member'
    item['submitted_by_name'] = item.get('submitted_by_name') or item.get('submitted_by') or 'Group Member'
    
    # Ensure defaults for UI
    item.setdefault('ai_status', None)
    item.setdefault('ai_latency', None)
    item.setdefault('quantity', 1)
        
    return item

def user_to_dict(user: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB user document to API-safe dictionary (masks password)."""
    if '_id' in user:
        user['_id'] = str(user['_id'])
    user.pop('password_hash', None)
    return user

"""
Data models and validation logic for Smart Cart.

Provides schema validation for Items, Users, and Groups with multi-tenancy support.
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import re

# Constants for validation
VALID_USER_ROLES = ['MANAGER', 'MEMBER']
VALID_STATUSES = ['PENDING', 'APPROVED', 'REJECTED', 'ERROR']
VALID_AI_STATUSES = ['CALCULATING', 'COMPLETED', 'ERROR']
MAX_ITEM_NAME_LENGTH = 200
DEFAULT_STATUS = 'PENDING'
DEFAULT_PRICE_NIS = 0.0

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

class ValidationError(Exception):
    """Raised when item validation fails."""
    pass

# --- Item Validation ---
def validate_item(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and prepare item data for insertion."""
    errors = []
    validated = {}

    if 'group_id' not in data or not data.get('group_id'):
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

    # Optional: category
    validated['category'] = str(data.get('category', 'OTHER')).strip()

    # Optional: submitted_by (The "who")
    validated['submitted_by'] = str(data.get('submitted_by', 'Anonymous')).strip()
    validated['submitted_by_name'] = str(data.get('submitted_by_name', 'Group Member')).strip() # Allow name

    # Optional: user_role
    if 'user_role' in data:
        if data['user_role'] not in VALID_USER_ROLES:
            errors.append(f'user_role must be one of: {", ".join(VALID_USER_ROLES)}')
        else:
            validated['user_role'] = data['user_role']

    # Optional: status
    if 'status' in data:
        if data['status'] not in VALID_STATUSES:
            errors.append(f'status must be one of: {", ".join(VALID_STATUSES)}')
        else:
            validated['status'] = data['status']
    else:
        validated['status'] = DEFAULT_STATUS

    # Optional: price_nis
    try:
        validated['price_nis'] = float(data.get('price_nis', DEFAULT_PRICE_NIS))
    except (ValueError, TypeError):
        errors.append('price_nis must be a valid number')

    # Optional: quantity
    try:
        validated['quantity'] = int(data.get('quantity', 1))
        if validated['quantity'] < 1:
            errors.append('quantity must be at least 1')
    except (ValueError, TypeError):
        errors.append('quantity must be a valid integer')

    # AI Fields
    if 'ai_status' in data:
        if data['ai_status'] not in VALID_AI_STATUSES:
             errors.append(f'ai_status must be one of: {", ".join(VALID_AI_STATUSES)}')
        else:
            validated['ai_status'] = data['ai_status']

    if 'ai_latency' in data:
        try:
            validated['ai_latency'] = float(data['ai_latency']) if data['ai_latency'] is not None else None
        except (ValueError, TypeError):
            errors.append('ai_latency must be a valid number or null')

    validated['created_at'] = data.get('created_at', datetime.now(timezone.utc))

    return validated, errors

# --- User Validation ---
def validate_user(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and prepare user data for insertion."""
    errors = []
    validated = {}

    # Required: email (unique)
    if 'email' not in data or not re.match(EMAIL_REGEX, data['email']):
        errors.append('A valid email address is required')
    else:
        validated['email'] = data['email'].lower().strip()

    # Required: password_hash
    if 'password_hash' not in data:
        errors.append('password_hash is required')
    else:
        validated['password_hash'] = data['password_hash']

    # Required: group_id
    if 'group_id' not in data:
        errors.append('group_id is required')
    else:
        validated['group_id'] = str(data['group_id'])

    # Required: role
    if 'role' not in data or data['role'] not in VALID_USER_ROLES:
        errors.append(f'role must be one of: {", ".join(VALID_USER_ROLES)}')
    else:
        validated['role'] = data['role']

    # Optional: full_name
    validated['full_name'] = str(data.get('full_name', '')).strip()
    validated['created_at'] = datetime.now(timezone.utc)

    return validated, errors

# --- Group Validation ---
def validate_group(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and prepare group data for insertion."""
    errors = []
    validated = {}

    # Required: name
    if 'name' not in data or not str(data['name']).strip():
        errors.append('group name is required')
    else:
        validated['name'] = str(data['name']).strip()

    # Required: join_code (generated if not present)
    import random, string
    validated['join_code'] = data.get('join_code', 
        ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)))

    validated['created_at'] = datetime.now(timezone.utc)
    validated['subscription_tier'] = data.get('subscription_tier', 'FREE')

    return validated, errors

def item_to_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB item document to API-safe dictionary for Group members."""
    if '_id' in item:
        item['_id'] = str(item['_id'])
    
    # Priority: 1. Human Name, 2. Submission Label, 3. 'Our Group'
    item['submitted_by_name'] = item.get('submitted_by_name') or item.get('submitted_by') or 'Group Member'
    
    if 'ai_status' not in item:
        item['ai_status'] = None
    if 'ai_latency' not in item:
        item['ai_latency'] = None
    if 'quantity' not in item:
        item['quantity'] = 1
        
    return item

def user_to_dict(user: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB user document to API-safe dictionary (removes password)."""
    if '_id' in user:
        user['_id'] = str(user['_id'])
    if 'password_hash' in user:
        del user['password_hash']
    return user

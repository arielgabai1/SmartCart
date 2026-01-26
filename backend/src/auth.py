import os
import datetime
import jwt
import bcrypt
from typing import Optional, Dict, Any, Tuple, List
from pymongo.collection import Collection
from flask import request, jsonify, g
from functools import wraps

from db import get_db
from models import validate_user, validate_group

SECRET_KEY = os.environ.get('JWT_SECRET', 'dev-secret-change-me')
ALGORITHM = 'HS256'

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_token(user_id: str, group_id: str, role: str, user_name: str, group_name: str, join_code: str = None) -> str:
    """Generate a JWT token enriched with names and Join Code."""
    payload = {
        'user_id': user_id,
        'group_id': group_id,
        'role': role,
        'user_name': user_name,
        'group_name': group_name,
        'join_code': join_code,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Unauthorized', 'details': 'Token is missing'}), 401
        
        data = decode_token(token)
        if not data:
            return jsonify({'error': 'Unauthorized', 'details': 'Token is invalid or expired'}), 401
        
        # Inject auth data into Flask's 'g' object
        g.user_id = data['user_id']
        g.group_id = data['group_id']
        
        # KEY FIX: Fetch fresh role from DB to support immediate promotion/demotion
        from flask import current_app
        from bson.objectid import ObjectId
        
        try:
            db = get_db()
            user = db['users'].find_one({'_id': ObjectId(data['user_id'])})
            if user:
                g.role = user.get('role', data['role']) # Use fresh role or fallback to token
                g.user_name = user.get('full_name', data.get('user_name', 'Anonymous')) # Fresh name too
            else:
                g.role = data['role']
                g.user_name = data.get('user_name', 'Anonymous')
        except Exception:
            # Fallback to token data if DB fails
            g.role = data['role']
            g.user_name = data.get('user_name', 'Anonymous')

        g.group_name = data.get('group_name', 'Group')
        g.join_code = data.get('join_code')
        
        return f(*args, **kwargs)
    return decorated

def register_group_and_admin(group_name: str, user_name: str, email: str, password: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Register a new group and its first admin (Manager)."""
    db = get_db()
    
    if db['users'].find_one({'email': email.lower().strip()}):
        return None, ['User with this email already exists']
    
    # 1. Create Group
    group_data, group_errors = validate_group({'name': group_name})
    if group_errors:
        return None, group_errors
    
    group_result = db['groups'].insert_one(group_data)
    group_id = str(group_result.inserted_id)
    join_code = group_data['join_code']
    
    # 2. Create Admin User
    user_data, user_errors = validate_user({
        'email': email,
        'password_hash': hash_password(password),
        'group_id': group_id,
        'role': 'MANAGER',
        'full_name': user_name
    })
    
    if user_errors:
        db['groups'].delete_one({'_id': group_result.inserted_id})
        return None, user_errors
    
    user_result = db['users'].insert_one(user_data)
    
    return {
        'user_id': str(user_result.inserted_id),
        'group_id': group_id,
        'role': 'MANAGER',
        'join_code': join_code
    }, []

def register_member_via_code(join_code: str, user_name: str, email: str, password: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Register a member to an existing group using its join code."""
    db = get_db()
    
    # Find group by code
    group = db['groups'].find_one({'join_code': join_code.upper().strip()})
    if not group:
        return None, ['Invalid Join Code']
        
    if db['users'].find_one({'email': email.lower().strip()}):
        return None, ['User with this email already exists']
        
    # Create Member User
    user_data, user_errors = validate_user({
        'email': email,
        'password_hash': hash_password(password),
        'group_id': str(group['_id']),
        'role': 'MEMBER',
        'full_name': user_name
    })
    
    if user_errors:
        return None, user_errors
        
    user_result = db['users'].insert_one(user_data)
    
    return {
        'user_id': str(user_result.inserted_id),
        'group_id': str(group['_id']),
        'role': 'MEMBER',
        'group_name': group['name']
    }, []

def login_user(email: str, password: str) -> Tuple[Optional[str], List[str]]:
    """Authenticate and return a name-enriched JWT."""
    db = get_db()
    user = db['users'].find_one({'email': email.lower().strip()})
    
    if not user or not verify_password(password, user['password_hash']):
        return None, ['Invalid email or password']
    
    # Fetch group name for the tokens
    from bson import ObjectId
    group = db['groups'].find_one({'_id': ObjectId(user['group_id'])})
    group_name = group['name'] if group else 'SmartCart Group'
    
    token = generate_token(
        str(user['_id']), 
        user['group_id'], 
        user['role'], 
        user.get('full_name', 'User'),
        group_name,
        group.get('join_code') if group else None
    )
    return token, []

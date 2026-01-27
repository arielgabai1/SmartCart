import logging
import sys
import os
import threading
from typing import Tuple, Any, Dict

from flask import Flask, jsonify, request, Response, g
from flask_cors import CORS
from dotenv import load_dotenv
from prometheus_client import make_wsgi_app, Counter
from bson import ObjectId
from pythonjsonlogger import jsonlogger
from werkzeug.serving import run_simple

import db
from db import get_db
from models import validate_item, item_to_dict
from auth import auth_required, register_group_and_admin, register_member_via_code, login_user
from ai_engine import estimate_item_price

# Load environment variables from .env file
load_dotenv()

# --- Configuration & Logging ---

def setup_logging() -> logging.Logger:
    """Configures JSON logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger

logger = setup_logging()

app = Flask(__name__)
CORS(app)

# --- Metrics ---

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])

# --- Helpers ---

def error_response(message: str, code: int = 400, details: Any = None) -> Tuple[Response, int]:
    """Standardized error response factory."""
    response = {'error': message}
    if details:
        response['details'] = details
    return jsonify(response), code

# --- Health Check ---

@app.route('/health')
def health() -> Tuple[Response, int]:
    """Health check endpoint for Kubernetes/Docker."""
    try:
        if db.db_client:
            db.db_client.admin.command('ping')
        return jsonify({'status': 'healthy'}), 200
    except Exception:
        return jsonify({'status': 'unhealthy'}), 503

# --- Auth Routes ---

@app.route('/api/auth/register', methods=['POST'])
def register() -> Tuple[Response, int]:
    """Register a new Group and its Admin (Manager)."""
    data = request.get_json()
    required = ('group_name', 'user_name', 'email', 'password')
    
    if not data or not all(k in data for k in required):
        return error_response('Missing required fields', 400)
    
    auth_data, errors = register_group_and_admin(
        data['group_name'], data['user_name'], data['email'], data['password']
    )
    
    if errors:
        return error_response('Registration failed', 400, errors)
    
    return jsonify({'message': 'Group created!', 'details': auth_data}), 201

@app.route('/api/auth/join', methods=['POST'])
def join() -> Tuple[Response, int]:
    """Join an existing Group via Join Code."""
    data = request.get_json()
    required = ('join_code', 'user_name', 'email', 'password')
    
    if not data or not all(k in data for k in required):
        return error_response('Missing required fields', 400)
    
    auth_data, errors = register_member_via_code(
        data['join_code'], data['user_name'], data['email'], data['password']
    )
    
    if errors:
        return error_response('Join failed', 400, errors)
    
    return jsonify({'message': 'Joined successfully!', 'details': auth_data}), 201

@app.route('/api/auth/login', methods=['POST'])
def login() -> Tuple[Response, int]:
    """Authenticate user and return JWT."""
    data = request.get_json()
    if not data or not all(k in data for k in ('email', 'password')):
        return error_response('Missing credentials', 400)
    
    token, errors = login_user(data['email'], data['password'])
    
    if errors:
        return error_response('Authentication failed', 401, errors)
    
    return jsonify({'token': token}), 200

@app.route('/api/auth/me', methods=['GET'])
@auth_required
def get_current_user() -> Tuple[Response, int]:
    """Return current user context."""
    return jsonify({
        'user_id': g.user_id,
        'user_name': g.user_name,
        'role': g.role,
        'group_id': g.group_id,
        'join_code': g.join_code
    }), 200

# --- Item Routes ---

@app.route('/api/items', methods=['GET'])
@auth_required
def get_items() -> Tuple[Response, int]:
    """Fetch all items for the user's group."""
    REQUEST_COUNT.labels(method='GET', endpoint='/api/items').inc()
    try:
        database = get_db()
        items = list(database['items']
                     .find({'group_id': g.group_id})
                     .sort('created_at', -1)
                     .limit(100))
        return jsonify([item_to_dict(item) for item in items]), 200
    except Exception as e:
        logger.error(f"Error fetching items: {e}")
        return error_response('Failed to fetch items', 500)

@app.route('/api/items', methods=['POST'])
@auth_required
def create_item() -> Tuple[Response, int]:
    """Create a new item and trigger AI estimation."""
    try:
        data = request.get_json(silent=True)
        if not data:
            return error_response('Invalid JSON', 400)

        # Enhance data with context
        data.update({
            'submitted_by': g.user_id,
            'submitted_by_name': g.user_name,
            'group_id': g.group_id,
            'ai_status': 'CALCULATING',
            'status': 'APPROVED' if g.role == 'MANAGER' else 'PENDING'
        })

        validated_item, errors = validate_item(data)
        if errors:
            return error_response('Validation failed', 400, errors)

        database = get_db()
        result = database['items'].insert_one(validated_item)
        item_id = result.inserted_id
        validated_item['_id'] = str(item_id)

        # Background AI Estimation
        def run_ai_task(cid: Any, name: str, cat: str):
            try:
                price, status = estimate_item_price(name, cat)
                database['items'].update_one(
                    {'_id': cid}, 
                    {'$set': {'price_nis': price, 'ai_status': status}}
                )
            except Exception as e:
                logger.error(f"AI update failed for item {cid}: {e}")

        threading.Thread(
            target=run_ai_task,
            args=(item_id, validated_item['name'], validated_item['category']),
            daemon=True
        ).start()

        return jsonify(item_to_dict(validated_item)), 201
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        return error_response('Internal error', 500)

@app.route('/api/items/<item_id>', methods=['PUT'])
@auth_required
def update_item(item_id: str) -> Tuple[Response, int]:
    """Update item status or quantity."""
    try:
        try:
            obj_id = ObjectId(item_id)
        except Exception:
            return error_response('Invalid item ID', 400)

        data = request.get_json()
        database = get_db()

        # Check existence and ownership (group)
        item = database['items'].find_one({'_id': obj_id, 'group_id': g.group_id})
        if not item:
            return error_response('Item not found', 404)

        update_fields = {}
        
        # Status Update (Manager Only)
        if 'status' in data:
            if g.role != 'MANAGER':
                return error_response('Only Managers can approve/reject items', 403)
            
            new_status = data['status']
            update_fields['status'] = new_status
            
            # Track rejection author
            if new_status == 'REJECTED':
                update_fields['rejected_by'] = g.user_id
                update_fields['rejected_by_name'] = g.user_name

        # Quantity Update
        if 'quantity' in data:
            try:
                # Permission check: Members can only edit their own PENDING items
                # Managers can edit any item
                if g.role != 'MANAGER':
                    is_owner = str(item.get('submitted_by')) == g.user_id
                    is_pending = item.get('status') == 'PENDING'
                    
                    if not (is_owner and is_pending):
                         return error_response('You can only update quantity on your own pending items', 403)

                qty = int(data['quantity'])
                if qty < 1:
                    return error_response('Quantity must be at least 1', 400)
                update_fields['quantity'] = qty
            except (ValueError, TypeError):
                return error_response('Invalid quantity', 400)

        if not update_fields:
            return error_response('No fields to update', 400)

        database['items'].update_one({'_id': obj_id}, {'$set': update_fields})
        return jsonify({'message': 'Updated successfully'}), 200
    except Exception as e:
        logger.error(f"Error updating item {item_id}: {e}")
        return error_response(str(e), 500)

@app.route('/api/items/<item_id>', methods=['DELETE'])
@auth_required
def delete_item(item_id: str) -> Tuple[Response, int]:
    """Delete an item (Manager or Owner)."""
    try:
        try:
            obj_id = ObjectId(item_id)
        except Exception:
            return error_response('Invalid item ID', 400)

        database = get_db()
        item = database['items'].find_one({'_id': obj_id, 'group_id': g.group_id})
        
        if not item:
            return error_response('Item not found', 404)

        is_owner = str(item.get('submitted_by')) == g.user_id
        if g.role != 'MANAGER' and not is_owner:
            return error_response('You can only delete your own items', 403)

        result = database['items'].delete_one({'_id': obj_id, 'group_id': g.group_id})
        if result.deleted_count == 0:
            return error_response('Item not found or already deleted', 404)
            
        return Response(status=204)
    except Exception as e:
        logger.error(f"Error deleting item {item_id}: {e}")
        return error_response('Internal error', 500)

@app.route('/api/items/clear', methods=['DELETE'])
@auth_required
def delete_all_items() -> Tuple[Response, int]:
    """Delete all items in the group (Manager only)."""
    try:
        if g.role != 'MANAGER':
            return error_response('Only Managers can clear the list', 403)

        database = get_db()
        database['items'].delete_many({'group_id': g.group_id})
        return Response(status=204)
    except Exception as e:
        logger.error(f"Error clearing items: {e}")
        return error_response(str(e), 500)

# --- Group Member Routes ---

@app.route('/api/groups/members', methods=['GET'])
@auth_required
def get_group_members() -> Tuple[Response, int]:
    """List all members of the group (Accessible to all members)."""
    try:
        # Removed Manager-only check to allow member visibility
            
        database = get_db()
        users = list(database['users'].find({'group_id': g.group_id}))
        
        member_list = [{
            'id': str(user['_id']),
            'user_name': user.get('full_name', 'Anonymous'),
            'email': user['email'],
            'role': user['role']
        } for user in users]
            
        return jsonify(member_list), 200
    except Exception as e:
        logger.error(f"Error getting members: {e}")
        return error_response(str(e), 500)

@app.route('/api/groups/members/<user_id>', methods=['PUT', 'DELETE'])
@auth_required
def manage_group_member(user_id: str) -> Tuple[Response, int]:
    """Promote, demote, or remove a member (Manager only)."""
    try:
        if g.role != 'MANAGER':
            return error_response('Only Managers can manage group members', 403)
            
        try:
            target_obj_id = ObjectId(user_id)
        except Exception:
            return error_response('Invalid user ID', 400)

        database = get_db()
        target_user = database['users'].find_one({'_id': target_obj_id, 'group_id': g.group_id})
        
        if not target_user:
            return error_response('User not found in your group', 404)
            
        if str(target_user['_id']) == g.user_id:
            return error_response('You cannot promote or remove yourself', 400)

        if request.method == 'DELETE':
            database['users'].delete_one({'_id': target_obj_id})
            return Response(status=204)
        
        elif request.method == 'PUT':
            data = request.get_json()
            new_role = data.get('role')
            if new_role not in ['MANAGER', 'MEMBER']:
                return error_response('Valid role (MANAGER or MEMBER) is required', 400)
            
            database['users'].update_one({'_id': target_obj_id}, {'$set': {'role': new_role}})
            return jsonify({'message': f'User role updated to {new_role}'}), 200
            
    except Exception as e:
        logger.error(f"Error managing member {user_id}: {e}")
        return error_response(str(e), 500)

# --- Server Start ---

def run_metrics_server() -> None:
    """Runs Prometheus metrics server on a separate port."""
    port = int(os.environ.get('METRICS_PORT', 8081))
    run_simple('0.0.0.0', port, make_wsgi_app(), threaded=True)

if __name__ == '__main__':
    # Start metrics server in background thread
    threading.Thread(target=run_metrics_server, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)


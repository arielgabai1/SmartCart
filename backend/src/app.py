import logging
import sys
import os
import threading
from typing import Tuple, Any


from flask import Flask, jsonify, request, Response, g
from flask_cors import CORS
from prometheus_client import make_wsgi_app, Counter, Histogram
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from bson.errors import InvalidId
from pythonjsonlogger import jsonlogger
from werkzeug.exceptions import BadRequest
from werkzeug.serving import run_simple

import db
from db import get_db
from models import validate_item, item_to_dict, VALID_STATUSES
from auth import auth_required, register_group_and_admin, register_member_via_code, login_user
from ai_engine import estimate_item_price

# JSON Logging Configuration
def setup_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger

logger = setup_logging()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])



@app.route('/health')
def health() -> Tuple[Response, int]:
    # Metrics port only (8081)
    try:
        if db.db_client:
            db.db_client.admin.command('ping')
        return jsonify({'status': 'healthy'}), 200
    except Exception:
        return jsonify({'status': 'unhealthy'}), 503

# --- Auth Routes ---
@app.route('/api/auth/register', methods=['POST'])
def register():
    """Start a new Group (Manager)."""
    data = request.get_json()
    if not data or not all(k in data for k in ('group_name', 'user_name', 'email', 'password')):
        return jsonify({'error': 'Missing required fields'}), 400
    
    auth_data, errors = register_group_and_admin(data['group_name'], data['user_name'], data['email'], data['password'])
    if errors:
        return jsonify({'error': 'Registration failed', 'details': errors}), 400
    
    return jsonify({'message': 'Group created!', 'details': auth_data}), 201

@app.route('/api/auth/join', methods=['POST'])
def join():
    """Join an existing Group (Member)."""
    data = request.get_json()
    if not data or not all(k in data for k in ('join_code', 'user_name', 'email', 'password')):
        return jsonify({'error': 'Missing required fields'}), 400
    
    auth_data, errors = register_member_via_code(data['join_code'], data['user_name'], data['email'], data['password'])
    if errors:
        return jsonify({'error': 'Join failed', 'details': errors}), 400
    
    return jsonify({'message': 'Joined successfully!', 'details': auth_data}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not all(k in data for k in ('email', 'password')):
        return jsonify({'error': 'Missing credentials'}), 400
    
    token, errors = login_user(data['email'], data['password'])
    if errors:
        return jsonify({'error': 'Authentication failed', 'details': errors}), 401
    
    return jsonify({'token': token}), 200

@app.route('/api/auth/me', methods=['GET'])
@auth_required
def get_current_user() -> Tuple[Response, int]:
    """Return the fresh database state (Role, Name) of the current user."""
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
    REQUEST_COUNT.labels(method='GET', endpoint='/api/items').inc()
    try:
        database = get_db()
        items = [item_to_dict(item) for item in database['items'].find({'group_id': g.group_id}).sort('created_at', -1).limit(100)]
        return jsonify(items), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch items'}), 500

@app.route('/api/items', methods=['POST'])
@auth_required
def create_item() -> Tuple[Response, int]:
    try:
        data = request.get_json(silent=True)
        if not data: return jsonify({'error': 'Invalid JSON'}), 400

        # Audit and Multi-tenancy
        data['submitted_by'] = g.user_id
        data['submitted_by_name'] = g.user_name  # KEY FIX: Save the actual user name
        data['group_id'] = g.group_id
        data['ai_status'] = 'CALCULATING' # Explicitly set for UI
        
        # Auto-approve for Managers
        data['status'] = 'APPROVED' if g.role == 'MANAGER' else 'PENDING'

        validated_item, errors = validate_item(data)
        if errors:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400

        database = get_db()
        result = database['items'].insert_one(validated_item)
        item_id = result.inserted_id
        validated_item['_id'] = str(item_id)

        # Async AI
        def run_ai(cid, name, cat):
            try:
                price, status = estimate_item_price(name, cat)
                database['items'].update_one(
                    {'_id': cid}, 
                    {'$set': {'price_nis': price, 'ai_status': status}}
                )
            except Exception as e:
                logger.error(f"Background update failed for item {cid}: {str(e)}")

        threading.Thread(
            target=run_ai,
            args=(item_id, validated_item['name'], validated_item['category']),
            daemon=True
        ).start()

        return jsonify(item_to_dict(validated_item)), 201
    except Exception as e:
        return jsonify({'error': 'Internal error'}), 500

@app.route('/api/items/<item_id>', methods=['PUT'])
@auth_required
def update_item(item_id: str) -> Tuple[Response, int]:
    try:
        obj_id = ObjectId(item_id)
        data = request.get_json()
        db = get_db()

        # Find item first to ensure it belongs to the group
        item = db['items'].find_one({'_id': obj_id, 'group_id': g.group_id})
        if not item:
            return jsonify({'error': 'Item not found'}), 404

        update_fields = {}
        
        # Status update: Managers only
        if 'status' in data:
            if g.role != 'MANAGER':
                return jsonify({'error': 'Only Managers can approve/reject items'}), 403
            update_fields['status'] = data['status']

        # Quantity update: Everyone
        if 'quantity' in data:
            try:
                qty = int(data['quantity'])
                if qty < 1:
                    return jsonify({'error': 'Quantity must be at least 1'}), 400
                update_fields['quantity'] = qty
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid quantity'}), 400

        if not update_fields:
            return jsonify({'error': 'No fields to update'}), 400

        db['items'].update_one({'_id': obj_id}, {'$set': update_fields})
        return jsonify({'message': 'Updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/groups/members', methods=['GET'])
@auth_required
def get_group_members() -> Any:
    try:
        if g.role != 'MANAGER':
            return jsonify({'error': 'Only Managers can view group members'}), 403
            
        db = get_db()
        # Find all users in the same group
        users = list(db['users'].find({'group_id': g.group_id}))
        
        member_list = []
        for user in users:
            member_list.append({
                'id': str(user['_id']),
                'user_name': user.get('full_name', 'Anonymous'),
                'email': user['email'],
                'role': user['role']
            })
            
        return jsonify(member_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/groups/members/<user_id>', methods=['PUT', 'DELETE'])
@auth_required
def manage_group_member(user_id: str) -> Any:
    try:
        if g.role != 'MANAGER':
            return jsonify({'error': 'Only Managers can manage group members'}), 403
            
        db = get_db()
        target_user = db['users'].find_one({'_id': ObjectId(user_id), 'group_id': g.group_id})
        
        if not target_user:
            return jsonify({'error': 'User not found in your group'}), 404
            
        # Cannot manage yourself
        if str(target_user['_id']) == g.user_id:
            return jsonify({'error': 'You cannot promote or remove yourself'}), 400

        if request.method == 'DELETE':
            db['users'].delete_one({'_id': ObjectId(user_id)})
            return ('', 204)
        
        elif request.method == 'PUT':
            data = request.get_json()
            new_role = data.get('role')
            if new_role not in ['MANAGER', 'MEMBER']:
                return jsonify({'error': 'Valid role (MANAGER or MEMBER) is required'}), 400
            
            db['users'].update_one({'_id': ObjectId(user_id)}, {'$set': {'role': new_role}})
            return jsonify({'message': f'User role updated to {new_role}'}), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/clear', methods=['DELETE'])
@auth_required
def delete_all_items() -> Any:
    try:
        if g.role != 'MANAGER':
            return jsonify({'error': 'Only Managers can clear the list'}), 403

        db = get_db()
        result = db['items'].delete_many({'group_id': g.group_id})
        return ('', 204)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/<item_id>', methods=['DELETE'])
@auth_required
def delete_item(item_id: str) -> Any:
    try:
        db = get_db()
        # Find item to check ownership
        item = db['items'].find_one({'_id': ObjectId(item_id), 'group_id': g.group_id})
        if not item:
            return jsonify({'error': 'Item not found'}), 404

        # Permission Check: Manager OR Owner
        is_owner = str(item.get('submitted_by')) == g.user_id
        if g.role != 'MANAGER' and not is_owner:
            return jsonify({'error': 'You can only delete your own items'}), 403

        # Single delete operation with correct criteria
        result = db['items'].delete_one({'_id': ObjectId(item_id), 'group_id': g.group_id})
        
        # If deleted count is 0, it means item wasn't found or already deleted
        if result.deleted_count == 0:
            return jsonify({'error': 'Item not found or already deleted'}), 404
            
        return ('', 204)
    except Exception:
        return jsonify({'error': 'Internal error'}), 500

def run_metrics_server():
    port = int(os.environ.get('METRICS_PORT', 8081))
    run_simple('0.0.0.0', port, make_wsgi_app(), threaded=True)


if __name__ == '__main__':
    threading.Thread(target=run_metrics_server, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)

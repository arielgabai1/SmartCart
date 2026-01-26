import logging
import os
import sys
import threading
import time

from flask import Flask, jsonify, request
from flask_cors import CORS
from prometheus_client import make_wsgi_app, Counter, Histogram
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from bson.errors import InvalidId
from pythonjsonlogger import jsonlogger
from werkzeug.exceptions import BadRequest
from werkzeug.serving import run_simple

# JSON Logging Configuration
def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    return logging.getLogger(__name__)

logger = setup_logging()

# Constants
DEFAULT_PRICE_NIS = 0.0
MAX_ITEM_NAME_LENGTH = 200
VALID_USER_ROLES = ['PARENT', 'KID']
VALID_STATUSES = ['PENDING', 'APPROVED', 'REJECTED']

# MongoDB Connection with Retry Loop (5 attempts)
def get_db_connection(max_retries=5, retry_delay=2):
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://database:27017/smartcart')

    for attempt in range(1, max_retries + 1):
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            logger.info('MongoDB connection established', extra={'attempt': attempt})
            return client
        except ConnectionFailure as e:
            logger.warning(
                'MongoDB connection failed, retrying...',
                extra={'attempt': attempt, 'max_retries': max_retries, 'error': str(e)}
            )
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                logger.error('MongoDB connection failed after max retries')
                raise
    return None

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')

# Lazy DB initialization
db_client = None
db = None

def get_db():
    global db_client, db
    if db_client is None:
        db_client = get_db_connection()
        db = db_client.get_database()
    return db

@app.route('/health')
def health():
    REQUEST_COUNT.labels(method='GET', endpoint='/health').inc()
    try:
        if db_client:
            db_client.admin.command('ping')
        return jsonify({'status': 'healthy', 'service': 'backend', 'db': 'connected' if db_client else 'not_initialized'})
    except Exception as e:
        logger.error('Health check failed', extra={'error': str(e)})
        return jsonify({'status': 'unhealthy', 'service': 'backend', 'error': str(e)}), 503


@app.route('/api/items', methods=['GET'])
def get_items():
    REQUEST_COUNT.labels(method='GET', endpoint='/api/items').inc()
    try:
        db = get_db()
        items = list(db['items'].find())
        for item in items:
            item['_id'] = str(item['_id'])
        logger.info('Items retrieved', extra={'count': len(items), 'endpoint': '/api/items'})
        return jsonify(items), 200
    except ConnectionFailure as e:
        logger.error('Database connection failed', extra={'error': str(e), 'endpoint': '/api/items'})
        return jsonify({'error': 'Database connection failed', 'details': str(e)}), 500
    except Exception as e:
        logger.error('Failed to fetch items', extra={'error': str(e), 'endpoint': '/api/items'})
        return jsonify({'error': 'Failed to fetch items', 'details': str(e)}), 500


@app.route('/api/items', methods=['POST'])
def create_item():
    REQUEST_COUNT.labels(method='POST', endpoint='/api/items').inc()
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON payload', 'details': 'Request body must be valid JSON'}), 400

        required_fields = ['name', 'user_role']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({'error': 'Missing required fields', 'details': f'Missing: {", ".join(missing)}'}), 400

        # Validate name is not empty or whitespace
        if not data['name'] or not data['name'].strip():
            return jsonify({'error': 'Invalid name', 'details': 'Name cannot be empty or whitespace'}), 400

        # Validate name length
        if len(data['name']) > MAX_ITEM_NAME_LENGTH:
            return jsonify({'error': 'Invalid name', 'details': f'Name cannot exceed {MAX_ITEM_NAME_LENGTH} characters'}), 400

        # Validate user_role
        if data['user_role'] not in VALID_USER_ROLES:
            return jsonify({'error': 'Invalid user_role', 'details': f'Must be one of: {", ".join(VALID_USER_ROLES)}'}), 400

        new_item = {
            'name': data['name'].strip(),
            'user_role': data['user_role'],
            'status': 'PENDING',
            'ai_status': 'CALCULATING',
            'price_nis': DEFAULT_PRICE_NIS
        }

        db = get_db()
        result = db['items'].insert_one(new_item)
        new_item['_id'] = str(result.inserted_id)
        logger.info('Item created', extra={'item_id': new_item['_id'], 'item_name': new_item['name']})
        return jsonify(new_item), 201
    except BadRequest as e:
        return jsonify({'error': 'Invalid JSON payload', 'details': str(e)}), 400
    except ConnectionFailure as e:
        logger.error('Database connection failed', extra={'error': str(e), 'endpoint': '/api/items'})
        return jsonify({'error': 'Database connection failed', 'details': str(e)}), 500
    except Exception as e:
        logger.error('Failed to create item', extra={'error': str(e), 'endpoint': '/api/items'})
        return jsonify({'error': 'Failed to create item', 'details': str(e)}), 500


@app.route('/api/items/<item_id>', methods=['PUT'])
def update_item(item_id):
    REQUEST_COUNT.labels(method='PUT', endpoint='/api/items/<id>').inc()
    try:
        obj_id = ObjectId(item_id)
    except InvalidId:
        return jsonify({'error': 'Invalid ID format', 'details': 'Item ID must be a valid ObjectId'}), 400

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON payload', 'details': 'Request body must be valid JSON'}), 400

        if 'status' not in data:
            return jsonify({'error': 'Missing required field', 'details': 'status field is required'}), 400

        if data['status'] not in VALID_STATUSES:
            return jsonify({'error': 'Invalid status', 'details': f'Must be one of: {", ".join(VALID_STATUSES)}'}), 400

        db = get_db()
        result = db['items'].update_one({'_id': obj_id}, {'$set': {'status': data['status']}})
        if result.matched_count == 0:
            return jsonify({'error': 'Item not found', 'details': f'No item with ID: {item_id}'}), 404

        updated_item = db['items'].find_one({'_id': obj_id})
        updated_item['_id'] = str(updated_item['_id'])
        logger.info('Item updated', extra={'item_id': item_id, 'status': data['status']})
        return jsonify(updated_item), 200
    except BadRequest as e:
        return jsonify({'error': 'Invalid JSON payload', 'details': str(e)}), 400
    except ConnectionFailure as e:
        logger.error('Database connection failed', extra={'error': str(e), 'endpoint': '/api/items/<id>'})
        return jsonify({'error': 'Database connection failed', 'details': str(e)}), 500
    except Exception as e:
        logger.error('Failed to update item', extra={'error': str(e), 'endpoint': '/api/items/<id>'})
        return jsonify({'error': 'Failed to update item', 'details': str(e)}), 500


@app.route('/api/items/<item_id>', methods=['DELETE'])
def delete_item(item_id):
    REQUEST_COUNT.labels(method='DELETE', endpoint='/api/items/<id>').inc()
    try:
        obj_id = ObjectId(item_id)
    except InvalidId:
        return jsonify({'error': 'Invalid ID format', 'details': 'Item ID must be a valid ObjectId'}), 400

    try:
        db = get_db()
        result = db['items'].delete_one({'_id': obj_id})
        if result.deleted_count == 0:
            return jsonify({'error': 'Item not found', 'details': f'No item with ID: {item_id}'}), 404

        logger.info('Item deleted', extra={'item_id': item_id})
        return '', 204
    except ConnectionFailure as e:
        logger.error('Database connection failed', extra={'error': str(e), 'endpoint': '/api/items/<id>'})
        return jsonify({'error': 'Database connection failed', 'details': str(e)}), 500
    except Exception as e:
        logger.error('Failed to delete item', extra={'error': str(e), 'endpoint': '/api/items/<id>'})
        return jsonify({'error': 'Failed to delete item', 'details': str(e)}), 500


def run_metrics_server():
    metrics_app = make_wsgi_app()
    run_simple('0.0.0.0', 8081, metrics_app, threaded=True)

if __name__ == '__main__':
    logger.info('Starting Smart Cart backend')
    metrics_thread = threading.Thread(target=run_metrics_server, daemon=True)
    metrics_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=False)

import logging
import sys
import threading

from flask import Flask, jsonify, request
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
from models import validate_item, item_to_dict

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

# Import constants from models for backward compatibility
from models import VALID_STATUSES

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')

@app.route('/health')
def health():
    REQUEST_COUNT.labels(method='GET', endpoint='/health').inc()
    try:
        if db.db_client:
            db.db_client.admin.command('ping')
        return jsonify({'status': 'healthy', 'service': 'backend', 'db': 'connected' if db.db_client else 'not_initialized'})
    except Exception as e:
        logger.error('Health check failed', extra={'error': str(e)})
        return jsonify({'status': 'unhealthy', 'service': 'backend', 'error': str(e)}), 503


@app.route('/api/items', methods=['GET'])
def get_items():
    REQUEST_COUNT.labels(method='GET', endpoint='/api/items').inc()
    try:
        database = get_db()
        items = [item_to_dict(item) for item in database['items'].find()]
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

        # Use schema validation from models.py
        validated_item, errors = validate_item(data)

        if errors:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400

        # Preserve ai_status if present in request (for backward compatibility)
        if 'ai_status' in data:
            validated_item['ai_status'] = data['ai_status']

        database = get_db()
        result = database['items'].insert_one(validated_item)
        validated_item['_id'] = str(result.inserted_id)

        logger.info('Item created', extra={
            'item_id': str(result.inserted_id),
            'item_name': validated_item['name'],
            'family_id': validated_item.get('family_id')
        })

        return jsonify(item_to_dict(validated_item)), 201
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

        database = get_db()
        result = database['items'].update_one({'_id': obj_id}, {'$set': {'status': data['status']}})
        if result.matched_count == 0:
            return jsonify({'error': 'Item not found', 'details': f'No item with ID: {item_id}'}), 404

        updated_item = database['items'].find_one({'_id': obj_id})
        logger.info('Item updated', extra={'item_id': item_id, 'status': data['status']})
        return jsonify(item_to_dict(updated_item)), 200
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

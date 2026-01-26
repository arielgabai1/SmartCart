import logging
import os
import sys
import threading
import time

from flask import Flask, jsonify
from flask_cors import CORS
from prometheus_client import make_wsgi_app, Counter, Histogram
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from pythonjsonlogger import jsonlogger
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



def run_metrics_server():
    metrics_app = make_wsgi_app()
    run_simple('0.0.0.0', 8081, metrics_app, threaded=True)

if __name__ == '__main__':
    logger.info('Starting Smart Cart backend')
    metrics_thread = threading.Thread(target=run_metrics_server, daemon=True)
    metrics_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=False)

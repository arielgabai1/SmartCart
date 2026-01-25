import threading
from flask import Flask, jsonify
from prometheus_client import make_wsgi_app, Counter, Histogram
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

app = Flask(__name__)

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')

@app.route('/health')
def health():
    REQUEST_COUNT.labels(method='GET', endpoint='/health').inc()
    return jsonify({'status': 'healthy', 'service': 'backend'})

@app.route('/api/items', methods=['GET'])
def get_items():
    REQUEST_COUNT.labels(method='GET', endpoint='/api/items').inc()
    return jsonify([])

def run_metrics_server():
    metrics_app = make_wsgi_app()
    run_simple('0.0.0.0', 8081, metrics_app, threaded=True)

if __name__ == '__main__':
    metrics_thread = threading.Thread(target=run_metrics_server, daemon=True)
    metrics_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=False)

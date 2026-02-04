import sys

# Add src directory to Python path
sys.path.insert(0, '/app/src')

# Worker configuration
workers = 1
threads = 4
worker_class = 'gthread'
bind = '0.0.0.0:5000'
timeout = 30
keepalive = 5
graceful_timeout = 30

# Logging - JSON format for access logs
errorlog = '-'
loglevel = 'warning'
accesslog = None  # Request logging handled by Flask after_request

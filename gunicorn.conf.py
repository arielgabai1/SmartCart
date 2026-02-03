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

# Logging - disable Gunicorn access log, use Flask's structured logging instead
accesslog = None
errorlog = '-'
loglevel = 'warning'

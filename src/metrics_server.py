import os
import time
import threading
from werkzeug.serving import run_simple
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app


def run_metrics_server(update_fn):
    """Run Prometheus metrics server on separate port.

    Args:
        update_fn: Function to call periodically to update metrics
    """
    def db_metrics_looper():
        while True:
            update_fn()
            time.sleep(5)

    threading.Thread(target=db_metrics_looper, daemon=True).start()

    app = DispatcherMiddleware(
        lambda _, r: r('404 Not Found', []) or [],
        {'/metrics': make_wsgi_app()}
    )
    port = int(os.environ.get('METRICS_PORT', 8081))
    run_simple('0.0.0.0', port, app, threaded=True)

FROM python:3.14.2-slim

RUN groupadd -r smartcartgroup && useradd -r -g smartcartgroup smartcart_user

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

COPY --chown=smartcart_user:smartcartgroup src/ ./src/
COPY --chown=smartcart_user:smartcartgroup tests/ ./tests/
COPY --chown=smartcart_user:smartcartgroup pytest.ini .

RUN chown smartcart_user:smartcartgroup /app
USER smartcart_user

CMD ["python", "src/app.py"]

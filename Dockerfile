FROM python:3.14.2-alpine

RUN addgroup -S smartcartgroup && adduser -S smartcart_user -G smartcartgroup

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.0 && \
    pip install --no-cache-dir -r requirements.txt && \
    apk add --no-cache curl

COPY --chown=smartcart_user:smartcartgroup src/ ./src/
COPY --chown=smartcart_user:smartcartgroup tests/ ./tests/
COPY --chown=smartcart_user:smartcartgroup pytest.ini .
RUN chown smartcart_user:smartcartgroup /app
USER smartcart_user

CMD ["gunicorn", "--config", "src/gunicorn.conf.py", "src.app:app"]

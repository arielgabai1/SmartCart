FROM python:3.14.2-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -r smartcartgroup && useradd -r -g smartcartgroup smartcart_user

COPY src/ ./src/
COPY tests/ ./tests/
COPY pytest.ini .

USER smartcart_user

CMD ["python", "src/app.py"]

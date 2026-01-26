FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -r smartcartgroup && useradd -r -g smartcartgroup smartcart_user

COPY src/ ./src/

USER smartcart_user

CMD ["python", "src/app.py"]

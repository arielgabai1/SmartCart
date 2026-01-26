FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser

CMD ["python", "src/app.py"]

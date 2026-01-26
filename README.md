# SmartCart

A family grocery list management application with multi-tenancy support and AI-powered price estimation.

## Overview

SmartCart is a web application that allows team/group members to collaboratively manage their shopping lists. Managers can approve or reject items, while members can add items to the list. The application features:

- Multi-tenant architecture with `family_id` isolation
- Dual-port Flask backend (public API on 5000, metrics on 8081)
- MongoDB for persistent data storage
- AI-powered price estimation
- Real-time updates via polling
- Prometheus metrics for monitoring

## Architecture

- **Frontend:** Nginx serving static HTML/CSS/JS
- **Backend:** Flask REST API with structured JSON logging
- **Database:** MongoDB with Docker volume persistence
- **Orchestration:** Docker Compose

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- OpenAI API key (for AI price estimation)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd SmartCart
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start the application**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Application: http://localhost
   - Metrics: http://localhost:8081/metrics
   - Health Check: http://localhost:5001/health

## MongoDB Data Persistence

### Volume Configuration

SmartCart uses Docker named volumes to persist MongoDB data across container restarts. The configuration in `docker-compose.yml` ensures your grocery list data is never lost.

**Volume Setup:**
```yaml
services:
  database:
    volumes:
      - mongodb_data:/data/db  # Named volume mounted to MongoDB data directory

volumes:
  mongodb_data:
    driver: local  # Docker-managed local volume
```

### Data Persistence Behavior

- **Survives:** Container restarts, `docker-compose down`, container recreation
- **Removed by:** `docker-compose down -v` (with -v flag) or `docker volume rm mongodb_data`
- **Location:** Docker-managed location (inspect with `docker volume inspect mongodb_data`)

### Backup Procedures

#### Manual Backup

Backup MongoDB data to a tar.gz archive:

```bash
# Stop the containers first (recommended)
docker-compose down

# Create backup
docker run --rm \
  -v smartcart_mongodb_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/mongodb-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .

# Restart containers
docker-compose up -d
```

#### Hot Backup (without stopping containers)

```bash
# Create backup while containers are running
docker run --rm \
  -v smartcart_mongodb_data:/data:ro \
  -v $(pwd):/backup \
  alpine tar czf /backup/mongodb-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
```

**Note:** Use `:ro` (read-only) flag to prevent accidental modifications during hot backup.

### Restore Procedures

#### Restore from Backup

```bash
# 1. Stop containers
docker-compose down

# 2. Remove existing volume (DANGER: This deletes current data!)
docker volume rm smartcart_mongodb_data

# 3. Recreate volume
docker volume create smartcart_mongodb_data

# 4. Restore from backup
docker run --rm \
  -v smartcart_mongodb_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/mongodb-backup-YYYYMMDD-HHMMSS.tar.gz -C /data

# 5. Restart containers
docker-compose up -d
```

#### Restore to New Environment

```bash
# Copy backup file to new environment
scp mongodb-backup-YYYYMMDD-HHMMSS.tar.gz user@newhost:/path/to/SmartCart/

# On new host, follow restore procedure above
```

### Volume Inspection

#### List Volumes
```bash
docker volume ls
```

#### Inspect Volume Details
```bash
docker volume inspect smartcart_mongodb_data
```

Output includes:
- Volume name
- Mount point on host
- Driver
- Created timestamp

#### Inspect Volume Contents
```bash
# List files in volume
docker run --rm \
  -v smartcart_mongodb_data:/data:ro \
  alpine ls -lah /data

# Search for specific MongoDB files
docker run --rm \
  -v smartcart_mongodb_data:/data:ro \
  alpine find /data -name "*.wt"
```

Expected files in MongoDB volume:
- `WiredTiger*` - Storage engine files
- `collection-*.wt` - Collection data files
- `index-*.wt` - Index files
- `mongod.lock` - Lock file

### Troubleshooting

#### Data Not Persisting

**Symptom:** Data disappears after restarting containers.

**Diagnosis:**
1. Check volume is mounted:
   ```bash
   docker inspect mongodb | grep -A 10 Mounts
   ```
2. Verify mount destination is `/data/db` (not `/data`)
3. Ensure volume name matches in both service and volumes sections

**Solution:**
- Verify `docker-compose.yml` volume configuration
- Check that you're not using `docker-compose down -v` which removes volumes

#### Permission Issues

**Symptom:** MongoDB fails to start with permission errors.

**Diagnosis:**
```bash
docker logs mongodb
```

**Solution:**
- Named volumes automatically handle permissions (MongoDB runs as UID 999)
- If using bind mounts (not recommended), fix with:
  ```bash
  sudo chown -R 999:999 ./data
  ```

#### Volume Full / Disk Space

**Symptom:** MongoDB writes fail, disk space errors.

**Diagnosis:**
```bash
# Check disk usage
df -h

# Check volume size
docker system df -v
```

**Solution:**
- Clean up unused volumes: `docker volume prune`
- Clean up unused images: `docker image prune`
- Monitor disk usage with Prometheus metrics

#### MongoDB Won't Connect After Restart

**Symptom:** Backend shows connection errors after restart.

**Diagnosis:**
```bash
# Check MongoDB logs
docker logs mongodb

# Check backend logs
docker logs SmartCart
```

**Solution:**
- SmartCart has built-in retry logic (5 attempts, 2s delay)
- Wait 10-15 seconds for MongoDB to fully start
- Verify health endpoint: `curl http://localhost:5001/health`

#### Lost Data After Update

**Symptom:** Volume exists but data is missing.

**Diagnosis:**
```bash
# Check if volume has data
docker run --rm \
  -v smartcart_mongodb_data:/data:ro \
  alpine ls -la /data

# Check volume mount in container
docker inspect mongodb | grep -A 10 Mounts
```

**Solution:**
- Verify volume name hasn't changed
- Check if wrong volume is mounted
- Restore from backup if data is truly lost

## Testing

### Unit Tests

Run unit tests without Docker:

```bash
cd backend
python -m pytest tests/unit/ -v
```

### API Tests

Run API tests (requires running containers):

```bash
cd backend
python -m pytest tests/api/ -v
```

### Integration Tests

Run persistence integration tests (requires Docker):

```bash
cd backend
python -m pytest tests/integration/ -v
```

Integration tests verify:
- Data persists after MongoDB container restart
- Data persists after full stack restart
- Volume contains MongoDB data files
- Connection retry logic works correctly

**Note:** Integration tests will stop and restart containers, so don't run them against production.

### Run All Tests

```bash
cd backend
python -m pytest -v --cov=src --cov-report=term-missing
```

## Development

### Local Setup (without Docker)

1. **Install dependencies**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run MongoDB locally**
   ```bash
   # Using Docker
   docker run -d -p 27017:27017 --name mongodb-dev mongo:8.2
   ```

3. **Run Flask app**
   ```bash
   export MONGO_URI=mongodb://localhost:27017/smartcart
   python src/app.py
   ```

### Project Structure

```
SmartCart/
├── docker-compose.yml       # Container orchestration
├── .env                     # Environment variables (git-ignored)
├── backend/
│   ├── src/
│   │   └── app.py          # Flask application
│   ├── tests/
│   │   ├── unit/           # Unit tests
│   │   ├── api/            # API integration tests
│   │   └── integration/    # Docker integration tests
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── Dockerfile
    └── nginx.conf

```

## Monitoring

### Health Check

```bash
curl http://localhost:5001/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "backend",
  "db": "connected"
}
```

### Prometheus Metrics

Access metrics at: http://localhost:8081/metrics

Available metrics:
- `http_requests_total` - Total HTTP requests by method and endpoint
- `http_request_duration_seconds` - Request latency histogram

## Multi-Tenancy

SmartCart uses `family_id` for data isolation. All MongoDB queries must include `family_id` to ensure proper tenant isolation.

**Example:**
```python
db['items'].find({'family_id': family_id})
```

## API Endpoints

### Public API (Port 5001)

- `GET /health` - Health check
- `GET /api/items` - List all items
- `POST /api/items` - Create item
- `PUT /api/items/:id` - Update item
- `DELETE /api/items/:id` - Delete item

### Metrics API (Port 8081)

- `GET /metrics` - Prometheus metrics

## License

[Your License Here]

## Contributing

[Contributing guidelines]

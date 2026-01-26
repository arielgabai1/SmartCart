# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SmartCart is a family grocery list management application with multi-tenancy (group isolation via `group_id`), role-based access control (MANAGER/MEMBER), and AI-powered price estimation using OpenAI.

## Architecture

Three-container setup orchestrated by Docker Compose:

1. **Frontend (Nginx)** - Port 80: Static serving + reverse proxy to backend `/api/`
2. **Backend (Flask)** - Port 5000 (internal), Port 8081 (metrics): Pure JSON REST API, zero HTML
3. **Database (MongoDB)** - Internal only: Persistent via Docker volumes

Key pattern: Frontend calls `/api/*` which Nginx proxies to `backend:5000`. Metrics exposed separately on 8081.

## Commands

### Development
```bash
# Start all services
docker-compose up -d

# Rebuild after code changes
docker-compose up -d --build

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Testing
```bash
# Run tests inside the backend container
docker-compose exec backend python -m pytest -v

# By type
docker-compose exec backend python -m pytest tests/unit/ -v
docker-compose exec backend python -m pytest tests/api/ -v

# By priority marker
docker-compose exec backend python -m pytest -m p0 -v   # Critical - every commit
docker-compose exec backend python -m pytest -m p1 -v   # High - every PR

# With coverage
docker-compose exec backend python -m pytest --cov=src --cov-report=term-missing
```

## Backend Source Layout

- `src/app.py` - Flask routes (auth + items + group management)
- `src/auth.py` - JWT auth, `@auth_required` decorator, user/group registration
- `src/models.py` - Schema validation for Items/Users/Groups
- `src/db.py` - MongoDB connection with retry logic
- `src/ai_engine.py` - OpenAI price estimation (async via threading)
- `src/seed.py` - Database seeding utilities

## Key Patterns

### Multi-tenancy
All queries must include `group_id` for tenant isolation:
```python
db['items'].find({'group_id': g.group_id})
```

### Auth Context
The `@auth_required` decorator populates Flask's `g` object:
- `g.user_id`, `g.group_id`, `g.role`, `g.user_name`, `g.join_code`

### Role-Based Access
- **MANAGER**: Can approve/reject items, delete items, manage members, clear list
- **MEMBER**: Can add items (PENDING status), update quantity

### AI Price Estimation
Runs async in background thread after item creation. Falls back to 15.0 NIS on error.

## Environment Variables

Copy `.env.example` to `.env`:
- `OPENAI_API_KEY` - For AI price estimation
- `MONGO_URI` - MongoDB connection string with auth
- `MONGO_INITDB_ROOT_USERNAME/PASSWORD` - MongoDB credentials
- `JWT_SECRET` - For token signing (defaults to dev value)

## API Endpoints

### Auth
- `POST /api/auth/register` - Create group + admin user
- `POST /api/auth/join` - Join group via join code
- `POST /api/auth/login` - Get JWT token
- `GET /api/auth/me` - Current user info (requires auth)

### Items (all require auth)
- `GET /api/items` - List items for group
- `POST /api/items` - Add item (auto-approved for MANAGER)
- `PUT /api/items/<id>` - Update status (MANAGER) or quantity (anyone)
- `DELETE /api/items/<id>` - Delete single item (MANAGER)
- `DELETE /api/items/clear` - Delete all group items (MANAGER)

### Group Management (MANAGER only)
- `GET /api/groups/members` - List group members
- `PUT /api/groups/members/<id>` - Update member role
- `DELETE /api/groups/members/<id>` - Remove member

## Test Markers

Defined in `pytest.ini`:
- `@pytest.mark.p0` - Critical, run every commit
- `@pytest.mark.p1` - High priority, run on PR
- `@pytest.mark.p2` - Medium, nightly
- `@pytest.mark.p3` - Low, on-demand
- `@pytest.mark.api` - API integration tests
- `@pytest.mark.unit` - Unit tests

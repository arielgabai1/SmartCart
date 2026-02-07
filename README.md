# SmartCart

<div align="center">

![Python](https://img.shields.io/badge/python-3.14.2-blue)
![Flask](https://img.shields.io/badge/flask-3.0-green)
![MongoDB](https://img.shields.io/badge/mongodb-8.2-brightgreen)
![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

**A collaborative family grocery list with AI-powered price estimation, multi-tenancy, and production-grade infrastructure.**

[Overview](#overview) · [Architecture](#architecture) · [Getting Started](#getting-started) · [API Reference](#api-reference) · [CI/CD](#cicd) · [Observability](#observability) · [Related Repos](#related-repositories)

</div>

## Overview

SmartCart lets families and groups manage shared grocery lists with role-based access control. Managers approve items submitted by members, while an AI engine (OpenAI gpt-4o-mini) estimates prices in NIS automatically. Each group is fully isolated via join codes and scoped data.

## Features

- **Multi-tenancy** -- groups isolated by join codes, all data scoped to `group_id`
- **Role-based access** -- MANAGER (full control, approve/reject) and MEMBER (submit items)
- **AI price estimation** -- OpenAI gpt-4o-mini estimates Israeli market prices in NIS
- **Production infrastructure** -- EKS cluster with CloudFront CDN serving static files from S3
- **GitOps** -- ArgoCD with sync-waves (ESO -> ClusterSecretStore -> SmartCart)
- **Observability** -- Prometheus + Grafana dashboards, EFK stack for log aggregation
- **CI/CD** -- Jenkins (main) + GitHub Actions (feature branches), security scanning pipeline
- **Auto-scaling** -- HPA (1-3 pods) + Karpenter for node provisioning

<p align="center">
  <img src="Screenshots/App/homepage.png" alt="SmartCart Dashboard" width="800">
</p>
<p align="center"><em>Manager dashboard -- shopping list, stats bar, add item form</em></p>

<p align="center">
  <img src="Screenshots/App/group.png" alt="Group Management" width="800">
</p>
<p align="center"><em>Group management sidebar -- invite code, member roles, promote/remove</em></p>

## Architecture

### Local Development

![Local Development -- 3-Tier Architecture](Diagrams/3Tier.png)

### Production

```mermaid
graph TB
    User --> CloudFront

    subgraph CDN
        CloudFront -->|static files| S3
        CloudFront -->|/api/*| Origin[origin.arielgabai.com]
    end

    Origin --> Ingress[Nginx Ingress]

    subgraph EKS Cluster
        Ingress --> Pods[SmartCart Pods<br>HPA 1-3]
        Pods --> MongoDB[MongoDB ReplicaSet]
        ArgoCD -->|sync| Pods
        ESO[External Secrets Operator] -->|inject| Pods
        ESO --> SecretsManager[AWS Secrets Manager]
        Prometheus -->|scrape :8081| Pods
        Prometheus --> Grafana
        FluentBit --> Elasticsearch --> Kibana
    end
```

## Tech Stack

- **Backend**: Python 3.14.2, Flask 3.0, Gunicorn 23.0, PyMongo 4.6.3, PyJWT 2.8, bcrypt 4.1, OpenAI SDK
- **Frontend**: Vanilla JS, S3 + CloudFront (prod), Nginx (dev)
- **Database**: MongoDB 8.2 (standalone dev, replica set prod)
- **Infrastructure**: AWS EKS, Karpenter, ArgoCD, External Secrets Operator, CloudFront + S3, Cloudflare DNS
- **Observability**: Prometheus, Grafana, Elasticsearch, Kibana, Fluent Bit
- **Testing**: pytest 8.0, mongomock, Playwright
- **Security**: Bandit, Trivy, pip-audit, SonarCloud

## Project Structure

```
SmartCart/
├── src/
│   ├── app.py              # Flask app, routes, middleware
│   ├── auth.py             # JWT, bcrypt, registration
│   ├── models.py           # Data validation, serialization
│   ├── ai_engine.py        # OpenAI price estimation
│   ├── db.py               # MongoDB connection with retry
│   ├── metrics_server.py   # Prometheus metrics (port 8081)
│   ├── metrics_utils.py    # DB metric collectors
│   └── gunicorn.conf.py    # 1 worker, 8 threads, port 5000
├── static/
│   ├── index.html           # Main app page
│   ├── login.html           # Login page
│   ├── register.html        # Registration page
│   ├── css/style.css
│   └── js/app.js            # Vanilla JS (auth, API, state, polling)
├── tests/
│   ├── unit_tests.py
│   ├── integration_tests.py
│   ├── e2e_tests.py
│   ├── conftest.py
│   └── bandit.yaml
├── dev/
│   ├── docker-compose.yml   # Local dev orchestration
│   ├── Dockerfile           # Nginx frontend image
│   └── conf.d/              # Nginx config (reverse proxy)
├── .github/workflows/
│   └── smartcart.yaml       # GitHub Actions (feature branches)
├── Dockerfile               # Backend image (python:3.14.2-alpine)
├── Jenkinsfile              # Main CI/CD pipeline
├── requirements.txt
├── pytest.ini
└── sonar-project.properties
```

<details>
<summary>Authentication screens</summary>

<p align="center">
  <img src="Screenshots/App/login.png" alt="Login" width="400">
</p>
<p align="center"><em>Login page</em></p>

<p align="center">
  <img src="Screenshots/App/signup-create.png" alt="Register - New Group" width="400">
</p>
<p align="center"><em>Registration -- create a new group</em></p>

</details>

## Getting Started

### Prerequisites

- Docker and Docker Compose
- An OpenAI API key (for price estimation)

### Setup

```bash
git clone https://gitlab.com/arielgabai/smartcart.git
cd SmartCart
```

Create `dev/.env`:

```env
JWT_SECRET=your-secret
MONGO_URI=mongodb://admin:password@mongodb:27017/smartcart?authSource=admin
OPENAI_API_KEY=your-openai-key
MONGO_INITDB_ROOT_USERNAME=admin
MONGO_INITDB_ROOT_PASSWORD=password
```

Start the stack:

```bash
docker compose -f dev/docker-compose.yml up --build -d
```

Access:
- **UI**: http://localhost
- **Metrics**: http://localhost:8081/metrics
- **Health**: http://localhost/api/health

Stop:

```bash
docker compose -f dev/docker-compose.yml down      # preserve data
docker compose -f dev/docker-compose.yml down -v    # reset data
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key for price estimation | **Required** |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `JWT_SECRET` | Secret for signing JWT tokens | **Required** |
| `MONGO_URI` | MongoDB connection string | **Required** |
| `METRICS_PORT` | Prometheus metrics port | `8081` |
| `MONGO_INITDB_ROOT_USERNAME` | MongoDB admin username | `admin` |
| `MONGO_INITDB_ROOT_PASSWORD` | MongoDB admin password | `password` |

## Local Development (without Docker)

```bash
# Start MongoDB
docker run -d -p 27017:27017 mongo:8.2

# Setup Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the app
export MONGO_URI="mongodb://localhost:27017/smartcart"
export JWT_SECRET="dev-secret"
export OPENAI_API_KEY="your-key"
python src/app.py
```

## Testing

```bash
# Unit tests
docker run --rm smartcart pytest tests/unit_tests.py --cov=src --tb=short

# Full stack (integration + E2E) -- requires running compose stack
docker compose -f dev/docker-compose.yml up -d --build
docker run --rm --network smartcart_frontend-net smartcart pytest tests/integration_tests.py --no-cov
```

**Markers**: `p0` (critical), `p1` (PR), `p2` (nightly), `p3` (on-demand), `unit`, `integration`, `e2e`

**Coverage threshold**: 80% (enforced by pytest.ini)

## CI/CD

### Jenkins (main + feature branches)

![Jenkins CI/CD Pipeline](Diagrams/Jenkins-CICD.png)

### GitHub Actions (feature branches)

![GitHub Actions CI Pipeline](Diagrams/GHA-CI.png)

## API Reference

All endpoints except auth and health require `Authorization: Bearer <token>`.

### Authentication

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create a new group and manager account |
| `POST` | `/api/auth/join` | Join existing group via join code |
| `POST` | `/api/auth/login` | Login, returns JWT token |
| `GET` | `/api/auth/me` | Current user context |

### Items

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/items` | List all group items |
| `POST` | `/api/items` | Add item (auto-triggers AI pricing) |
| `PUT` | `/api/items/<id>` | Update status (Manager) or quantity |
| `DELETE` | `/api/items/<id>` | Delete item (Manager or owner) |
| `DELETE` | `/api/items/clear` | Clear all items (Manager only) |

### Group Management

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/groups/members` | List group members |
| `PUT` | `/api/groups/members/<id>` | Change member role |
| `DELETE` | `/api/groups/members/<id>` | Remove member (Manager only) |

### Health & Metrics

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check (K8s/Docker probe) |
| `GET` | `:8081/metrics` | Prometheus metrics |

## Observability

### Prometheus Metrics

| Metric | Type | Description |
|---|---|---|
| `http_requests_total` | Counter | Total HTTP requests (method, endpoint, status) |
| `http_request_duration_seconds` | Histogram | Request latency (method, endpoint) |
| `db_connections_active` | Gauge | Active MongoDB connections |
| `application_start_time_seconds` | Gauge | App start timestamp |
| `auth_events_total` | Counter | Auth events (event, status) |
| `items_total` | Gauge | Total items in database |
| `ai_estimations_total` | Counter | Total AI price estimations |
| `ai_estimation_duration_seconds` | Histogram | AI estimation latency (status) |
| `ai_errors_total` | Counter | AI pricing errors |

### Logging

Structured JSON logs with trace IDs, user context, and request metadata. Collected by Fluent Bit and shipped to Elasticsearch with Kibana dashboards.

<p align="center">
  <img src="Screenshots/Dashboards/Grafana-SmartCart.png" alt="Grafana SmartCart Dashboard" width="800">
</p>
<p align="center"><em>Grafana -- application metrics (health, user impact, AI estimation)</em></p>

<p align="center">
  <img src="Screenshots/Dashboards/Kibana.png" alt="Kibana Dashboard" width="800">
</p>
<p align="center"><em>Kibana -- log analytics (volume, HTTP codes, errors, recent logs)</em></p>

## Related Repositories

- [SmartCart-Terraform](https://gitlab.com/arielgabai/smartcart-terraform) -- AWS EKS infrastructure (VPC, EKS, CloudFront CDN, Cloudflare DNS)
- [SmartCart-GitOps](https://gitlab.com/arielgabai/smartcart-gitops) -- ArgoCD application manifests and Helm chart

## License

MIT

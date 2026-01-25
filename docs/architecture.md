# System Architecture Document: Smart Cart

| Metadata | Details |
| :--- | :--- |
| **Project** | Smart Cart (Israel Budget Guard) |
| **Version** | 1.0 |
| **Status** | **APPROVED** |
| **Architect** | Winston |
| **Inputs** | prd.md, ux-design.md, Technical constraints (Nginx/Flask Split) |

## 1. Executive Summary
Smart Cart is a distributed web application designed to manage family grocery lists. Unlike the previous monolithic design, **Version 2.0** strictly separates concerns to ensure independent deployability and a smoother DevOps experience.

**Key Architectural Decisions:**
1.  **The "Sidecar" Pattern:** The application runs as a composed set of containers. The **Frontend (Nginx)** acts as the single entry point and reverse proxy, shielding the **Backend (Flask)** from direct user traffic.
2.  **Pure JSON API:** The Flask backend renders *zero* HTML. It accepts JSON and returns JSON. This allows the backend to be swapped, upgraded, or scaled independently of the UI.
3.  **Vanilla JS Polling:** The frontend remains lightweight (no build steps like Webpack/Vite). Configuration relies on **relative paths** (`/api/...`), utilizing Nginx to route requests to the correct internal container.
4.  **Dual-Plane Observability:**
    * **User Plane (Port 80):** Served by Nginx (UI + API proxy).
    * **Control Plane (Port 8081):** Served by Flask directly (Prometheus Metrics only). This ensures that heavy monitoring traffic does not clog the user's API pipe.

## 2. High-Level Architecture (The "Three Container" Setup)
The system consists of three primary containers running on a single Docker host:



### 2.1 Container 1: The Gateway (Nginx)
* **Base Image:** `nginx:alpine` (Tiny, secure).
* **External Port:** `80` (The only port the user interacts with).
* **Responsibilities:**
    * **Static Serving:** Serves HTML/CSS/JS assets from `/usr/share/nginx/html`.
    * **Reverse Proxy:** Forwards all traffic starting with `/api/` to the `backend` container on port 5000.
    * **Security:** Hides the internal topology from the client.

### 2.2 Container 2: The Logic (Flask)
* **Base Image:** `python:3.10-slim`.
* **Internal Port:** `5000` (Business Logic - NOT exposed to host).
* **External Port:** `8081` (Observability - Exposed to host).
* **Responsibilities:**
    * **API Layer:** Handles REST requests (`GET`, `POST`, `PUT`, `DELETE`).
    * **Worker Layer:** Spawns background threads for external AI calls to OpenAI.
    * **Metrics Layer:** Exposes `/metrics` for Prometheus on port 8081.

### 2.3 Container 3: The State (MongoDB)
* **Base Image:** `mongo:6.0`.
* **Responsibilities:** Persist data via Docker Volumes.

## 3. Technology Stack

### 3.1 Frontend Layer
* **Server:** Nginx.
* **Language:** HTML5, CSS3, Vanilla JavaScript (ES6+).
* **Frameworks:** None. Zero dependencies.
* **Communication:** Native `fetch()` API using relative paths (e.g., `fetch('/api/items')`).

### 3.2 Backend Layer
* **Runtime:** Python 3.10+.
* **Web Framework:** Flask (Headless mode).
* **Concurrency:** Python `threading` module (for non-blocking AI calls).
* **Database Driver:** `pymongo`.

### 3.3 Data & Intelligence
* **Database:** MongoDB Community Edition (v6.0+).
* **AI Service:** OpenAI API (Model: `gpt-4o-mini`).
* **Observability:** Prometheus Python Client.

## 4. Component Design

### 4.1 Data Model (Schema)
**Database:** `shop_db` | **Collection:** `items`

| Field | Type | Description |
| :--- | :--- | :--- |
| `_id` | `ObjectId` | Unique identifier. |
| `name` | `String` | Raw input (e.g., "Milk"). |
| `user_role` | `String` | "PARENT" or "KID". |
| `status` | `String` | "PENDING", "APPROVED", "REJECTED". |
| `price_nis` | `Float` | Estimated price (NIS). |
| `ai_status` | `String` | "CALCULATING", "COMPLETED", "ERROR". |
| `ai_latency`| `Float` | Time (seconds) for AI response. |

### 4.2 API Specification (REST - JSON Only)

#### 1. Fetch Items
* **Endpoint:** `GET /api/items`
* **Response:** JSON Array of item objects.

#### 2. Add Item
* **Endpoint:** `POST /api/items`
* **Payload:** `{ "name": "Bamba", "user_role": "KID" }`
* **Response:** HTTP 201 (Processing started).

#### 3. Update Status
* **Endpoint:** `PUT /api/items/<id>`
* **Payload:** `{ "status": "APPROVED" }`

#### 4. Delete Item
* **Endpoint:** `DELETE /api/items/<id>`

## 5. Directory Layout & Standards
This structure supports **independent deployment** of frontend and backend.

```text
smart-family-shop/
├── docker-compose.yml       # Orchestrates Nginx + Flask + Mongo
├── .env                     # Secrets (OPENAI_KEY, MONGO_URI) - DO NOT COMMIT
├── .gitignore
├── README.md
├── frontend/                # [DEPLOYABLE UNIT: UI]
│   ├── Dockerfile           # Nginx configuration
│   ├── nginx.conf           # Reverse proxy rules
│   └── src/                 # Static Assets
│       ├── index.html
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── app.js
├── backend/                 # [DEPLOYABLE UNIT: API]
│   ├── Dockerfile           # Python configuration
│   ├── requirements.txt
│   └── src/
│       ├── app.py           # API Routes only
│       ├── ai.py            # OpenAI logic
│       └── db.py            # DB Connection
└── data/                    # Local DB volume (git-ignored)

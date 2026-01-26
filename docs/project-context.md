# Project Context: Smart Cart

## 1. Architecture Constraints
* **Multi-Tenancy:** Must use `family_id` in ALL MongoDB queries to isolate data between families.
* **Network Isolation:** * Public Routes (`/`, `/api`) -> Bind 0.0.0.0:5000
    * Private Routes (`/metrics`, `/admin`) -> Bind 0.0.0.0:8081 (Threaded)
* **Persistence:** Docker Volume `./data:/data/db` is MANDATORY.

## 2. Data Dictionary (Schema)
**User:**
* `user_id` (UUID), `family_id` (UUID), `role` (manager/member), `password_hash`

**Item:**
* `item_id` (UUID), `family_id` (UUID), `name` (Str), `price_nis` (Float), `status` (approved/pending), `created_at` (Timestamp)

## 3. AI & Logic Rules
* **Price Fallback:** If AI fails or returns non-numeric, default to `15.0` NIS.
* **Budget Guard:** Sum of `price_nis` for all `status='approved'` items.
* **Concurrency:** Client uses `setInterval(3000)` to fetch updates. Backend uses `Last-Write-Wins`.

## 4. Implementation Priorities (Day 1)
1.  **Skeleton:** `app.py` with Threaded Metrics.
2.  **Database:** `models.py` with `family_id` logic.
3.  **UI:** `index.html` with Role switching query param (`?role=manager`).
4.  **AI:** `ai_engine.py` connected to OpenAI.

## 5. Known Pain Points & Mitigations
* **Startup Race:** DB Connection must use a `Retry Loop` (5 attempts).
* **Zombie Processes:** Threads must be `daemon=True`.
* **Logging:** Must use `python-json-logger` for future Loki integration.
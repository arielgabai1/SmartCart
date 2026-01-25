# Product Requirements Document (PRD): Smart Cart

| Metadata | Details |
| :--- | :--- |
| **Product** | Smart Cart |
| **Version** | 1.0 (Frozen for MVP) |
| **Status** | **APPROVED** |
| **Owner** | John (PM) |
| **Input Source** | product-brief.md, User Decisions |

## 1. Introduction & Strategic Fit
**Vision:** To build a "DevOps-Ready" family grocery application that balances financial control for parents with a robust, observability-first engineering playground, tailored for the Israeli market context ("Israel Budget Guard").

**Why we are building this:**
1.  **User Value:** Families lack real-time visibility into grocery "sticker shock" before checkout.
2.  **Dev Value:** A lightweight "pet lab" to demonstrate competence in Observability and full-stack integration without heavy cloud costs.

## 2. User Personas
* **The "CFO" Parent (Admin/User):** * **Goal:** Control the family budget.
    * **Pain Point:** Kids adding random expensive items without approval.
    * **Needs:** Approval capability and a "Total Estimated Cost" view in NIS.
* **The "Requestor" Kid (User):** * **Goal:** Get snacks (e.g., Bamba, Candy).
    * **Pain Point:** Not knowing if their request was seen or denied.
    * **Needs:** Simple "Add" interface; clear visual feedback if an item is rejected.

## 3. Functional Requirements

### 3.1 Core List Management (The "Live Sync" Engine)
* **FR-01:** System MUST support real-time list synchronization across clients via aggressive polling (approx. 3s interval).
* **FR-02:** Users (All) MUST be able to Create, Read, Update, and Delete (CRUD) list items.
* **FR-03:** Frontend MUST utilize Optimistic UI updates to ensure perceived zero-latency for the user.

### 3.2 Role-Based Financial Control
* **FR-04 (Kid View):** Users identified as "Kid" MUST ONLY be able to "Request" items. They CANNOT view the running Budget total.
* **FR-05 (Parent View):** Users identified as "Parent" MUST have an "Approval Queue" view to Approve or Reject kid requests.
* **FR-06 (Rejection Logic):** * If a Parent rejects an item, it MUST remain on the list but visually change to a **"REJECTED" state** (e.g., Red text, strikethrough, or "Rejected" label).
    * This prevents the "Vanishing Item Loop" where a kid re-adds an item thinking it was deleted by a glitch.

### 3.3 The "Israel Budget Guard" (AI Pricing)
* **FR-07:** System MUST automatically trigger an AI estimation (OpenAI GPT-4o-mini) for every new item added.
* **FR-08 (Estimation Strategy):** * The AI MUST return the **Average Market Price** in New Israeli Shekels (NIS).
    * It should assume standard generic brands (e.g., "Milk" = Average price of 1L generic milk) unless a specific brand is named.
* **FR-09:** The Total Budget calculation MUST update immediately upon item addition (for Parents).
* **FR-10 (Error Handling):** If the AI service fails or times out, the system MUST default the price to 0 and flag the item as "Price Unavailable" (Non-blocking failure).

### 3.4 DevOps & Observability
* **FR-11:** System MUST expose a `/metrics` endpoint compatible with Prometheus.
* **FR-12:** Metric `ai_latency_seconds` MUST be tracked to monitor the performance of the pricing engine.

## 4. Non-Functional Requirements (NFRs)
* **Architecture:** Dual-Port Architecture (Flask). 
    * Port 5000: App Traffic.
    * Port 8081: Metrics/Admin.
* **Persistence:** MongoDB running as a local container with host volume persistence.
* **Performance:** AI Pricing estimation MUST operate asynchronously; it must not block the UI or the main application thread.
* **Constraint:** **NO "Panic Mode" Chaos Engineering features for MVP.** Focus on stability.

## 5. Success Metrics (KPIs)
1.  **Accuracy:** Budget estimation within **15%** of actual receipt total.
2.  **Performance:** 95th percentile of `ai_latency_seconds` < 2.0s.
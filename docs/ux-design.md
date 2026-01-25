# UX Design & UI Plan: Smart Cart

| Metadata | Details |
| :--- | :--- |
| **Project** | Smart Cart |
| **Version** | 1.0 (MVP) |
| **Status** | **APPROVED** |
| **Designer** | Sally (UX) |
| **Source** | prd.md |

## 1. Executive Summary
This design bridges the gap between the "Requestor" (Kid) and the "CFO" (Parent). The core UX challenge is managing the latency of AI pricing without disrupting the user's flow, while simultaneously preventing the emotional friction of "vanishing items" when requests are rejected.

## 2. Core UX Strategy

### 2.1 The "Optimistic" Interaction Model
To satisfy the requirement for "perceived zero-latency" (FR-03), all user actions must feel instant.
* **Action:** User adds "Milk".
* **Immediate Feedback:** Item appears on the list with a temporary ID.
* **Background Process:** System syncs with backend and triggers AI pricing.
* **Visual State:** Price shows a "calculating" skeleton loader until data returns.

### 2.2 The "No-Vanish" Rejection Policy
To solve the Kid's pain point of uncertainty:
* **Current Behavior (Bad):** Item is deleted. Kid thinks the app broke.
* **New Behavior (Good):** Rejected items remain on the list but change visual state (Strikethrough + Red "Rejected" badge). This provides closure.

### 2.3 Visualizing Observability (The "DevOps" Twist)
Since this is a tech playground:
* **AI Latency:** We will expose the backend `ai_latency_seconds` metric visually by modulating the duration of the "price shimmering" animation.

## 3. Information Architecture

### Sitemap
The application is a Single Page Application (SPA) with state-based views.
# Product Brief: Smart Cart 

## 1. Vision & Scope
**Product Name:** Smart Cart
**Mission:** Create a "DevOps-Ready" 3-tier family grocery application that demonstrates advanced architectural patterns (Observability, Security, AI Integration) without heavy infrastructure overhead.
**Target Audience:** Families who need collaborative list management with financial intelligence; Recruiters/Engineers evaluating DevOps competency.

## 2. Core Value Propositions
* **The "Israel Budget Guard":** AI-driven price estimation using real-time Israeli market data (NIS) to track family spending.
* **Role-Based Command Center:** Hierarchical access (Manager vs. Member) ensuring financial control.
* **DevOps Native:** Built from day one with Observability (Prometheus), Chaos Engineering (Panic Mode), and Security (Network Isolation) in mind.

## 3. Technical Foundation (The "No-Infra" Stack)
* **Frontend:** Vanilla HTML5/CSS3/JS (Optimistic UI updates).
* **Backend:** Python Flask (Dual-Port Architecture).
    * Port 5000: Application Traffic.
    * Port 8081: Telemetry & Admin Console.
* **Database:** MongoDB (Local Container, Host Volume Persistence).
* **AI Engine:** OpenAI API (GPT-4o-mini) for Pricing & Suggestions.

## 4. Key Features
| Feature | User | Description |
| :--- | :--- | :--- |
| **Live Sync** | All | Real-time list updates via aggressive polling (3s). |
| **Role Limits** | Member | Can only "Request" items. cannot see Budget. |
| **Approval Queue** | Manager | Review and Approve/Reject member requests. |
| **Smart Price** | System | Auto-estimates NIS price for every item via AI. |
| **Panic Mode** | Admin | Simulated system failure trigger for testing alerts. |

## 5. Success Metrics
* **User Metric:** Accurate Budget estimation within 15% of actual receipt.
* **DevOps Metric:** `ai_latency_seconds` visible on Prometheus.
* **System Metric:** 99.9% uptime during "Panic Mode" recovery tests.
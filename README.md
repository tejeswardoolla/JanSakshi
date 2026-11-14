# JanSakshi — AI-Powered Civic Complaint Verification and Municipal Accountability System

<div align="center">
  <img src="frontend/public/assets/jansakshi-logo.jpg" width="130" alt="JanSakshi Logo" />

  ### Citizen Reports. AI Verifies. Accountability Delivers.

  [![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.12-009688.svg)](https://fastapi.tiangolo.com/)
  [![React](https://img.shields.io/badge/Frontend-React%2018%20%7C%20Vite-61DAFB.svg)](https://react.dev/)
  [![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind%20CSS-38B2AC.svg)](https://tailwindcss.com/)
  [![Gemini AI](https://img.shields.io/badge/AI-Google%20Gemini%20Multimodal-8E75C2.svg)](https://ai.google.dev/)
  [![License](https://img.shields.io/badge/License-Academic%20%2F%20MIT-blue.svg)](LICENSE)
</div>

---

## Executive Summary

**JanSakshi** (*The People's Witness*) is a next-generation civic grievance verification and municipal accountability platform designed for Indian urban local bodies. Traditional civic portals suffer from duplicate complaint backlogs, spam emails, unverified closures, and lack of field accountability.

JanSakshi solves these challenges through:
1. **Multimodal Citizen Reporting:** Web portal with GPS pin-dropping, category taxonomy, and photo/video evidence capture.
2. **Phase 6 Gmail AI Grievance Desk:** Automated Gmail API ingestion using a 4-layer intent classifier that prevents spam/transactional emails from becoming complaints while providing automated citizen tracking acknowledgements.
3. **Phase 4 Multimodal Vision Analysis:** Google Gemini AI analyzes evidence photos, verifies civic damage, estimates severity, and flags safety hazards.
4. **Phase 5 Multi-Factor Duplicate Detection:** Spatial proximity (Haversine), textual similarity (TF-IDF/cosine), and category matching group redundant reports under single **Physical Issues**.
5. **Phase 7 & 8 Role-Based Municipal Operations:** End-to-end governance lifecycle with distinct portals for:
   - **Municipal Administrator:** Triage, duplicate merging, Gmail desk review, and system auditing.
   - **Authority Officer:** Dispatching complaints to municipal departments with SLA deadlines.
   - **Department Field Officer (e.g., Roads & Public Works):** Field inspections, contractor work order assignment, before/after evidence upload, and version-controlled resolution submission.
   - **Resolution Review & Approval Desk:** Quality assurance approving or returning field repairs with audit history.

---

## System Architecture

```
                                  [ Citizen Reports ]
                                  /                 \
                      Web Portal (React + Vite)   Email Grievance (Gmail API)
                                  \                 /
                                   v               v
                   +-----------------------------------------------+
                   |             FastAPI Core Gateway              |
                   |  (JWT Auth + Single-Use Refresh Token Lock)   |
                   +-----------------------------------------------+
                                          |
                +-------------------------+-------------------------+
                |                         |                         |
                v                         v                         v
       [ 4-Layer Intent ]        [ Multimodal Vision ]     [ Multi-Factor Engine ]
     Spam & Non-Civic Filter      Google Gemini 2.5/3.8     Duplicate Detection &
     & Human Review Desk           Damage Verification      Physical Issue Grouping
                |                         |                         |
                +-------------------------+-------------------------+
                                          |
                                          v
                   +-----------------------------------------------+
                   |           Municipal Operations Hub            |
                   |  Admin Desk | Authority Dispatch | Dept Ops   |
                   +-----------------------------------------------+
                                          |
                                          v
                   +-----------------------------------------------+
                   |      Multi-Version Resolution QA Desk         |
                   |   Before/After Photo Verification & Sign-off  |
                   +-----------------------------------------------+
```

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, Vite, Tailwind CSS, Framer Motion, Lucide React, Leaflet Maps |
| **Backend** | Python 3.12, FastAPI, Uvicorn, SQLAlchemy ORM, Pydantic v2 |
| **Database** | SQLite (Default for zero-config local dev; swappable to PostgreSQL / Supabase) |
| **AI / ML** | Google Gemini Multimodal Vision API, Scikit-learn (TF-IDF cosine similarity) |
| **Email Subsystem** | Google Gmail API (OAuth 2.0 / Service Token), 4-Layer Hybrid Intent Classifier |
| **Security** | Short-lived JWT (30-min), Cryptographic Rotating Refresh Tokens, JTI Server Revocation |

---

## Project Structure

```
JanSakshi/
├── backend/
│   ├── app/
│   │   ├── core/           # Security, JWT tokens, config, CORS
│   │   ├── database.py     # SQLAlchemy database connection & session
│   │   ├── main.py         # FastAPI application entrypoint
│   │   ├── models/         # SQLAlchemy ORM models (Complaints, Users, Email, Issues)
│   │   ├── pipeline/       # Unified complaint processing pipeline
│   │   ├── routes/         # Modular API routers (Auth, Complaints, Authority, Email)
│   │   ├── schemas.py      # Pydantic validation models
│   │   └── services/       # AI, duplicate detection, email, resolution services
│   ├── requirements.txt    # Python dependencies
│   ├── .env.example        # Environment template (NO secrets)
│   └── test_*.py           # Comprehensive automated verification test suites
├── frontend/
│   ├── public/             # Static hero banners, icons, issue category imagery
│   ├── src/
│   │   ├── components/     # Authority layout, navbar, map pickers, file uploaders
│   │   ├── context/        # AuthContext with silent JWT refresh & 401 interception
│   │   ├── pages/          # Citizen portal, tracking, admin, authority, dept workspaces
│   │   └── styles/         # Global styles & design tokens
│   ├── package.json        # Node.js dependencies
│   └── vite.config.js      # Vite dev server configuration
├── Screenshots/            # System evidence & live application captures
├── README.md               # Project documentation
└── .gitignore              # Airtight git exclude rules
```

---

## Quickstart & Installation

### 1. Prerequisites
- **Python:** 3.11 or 3.12
- **Node.js:** v18 or later (npm v9+)
- **Git**

---

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration template
copy .env.example .env    # Windows
cp .env.example .env      # Linux / macOS

# Start FastAPI development server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Backend API:** `http://127.0.0.1:8000`
- **Swagger / OpenAPI Documentation:** `http://127.0.0.1:8000/api/docs`
- **Health Check Endpoint:** `http://127.0.0.1:8000/api/health`

---

### 3. Frontend Setup

```bash
# In a new terminal, navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```

- **Application URL:** `http://localhost:5173`

---

## Default Demonstration Credentials

For local evaluation and demonstration, the application seeds standard role-based accounts:

| Role | Username | Password | Access Scope |
|---|---|---|---|
| **Municipal Administrator** | `admin` | `JanSakshi@2026` | Intake Triage, Duplicate Review, Gmail Desk, System Audit |
| **Authority Officer** | `authority_officer` | `JanSakshi@2026` | Verification Queue, Department Dispatch, Resolution QA |
| **Roads Field Officer** | `roads_officer` | `JanSakshi@2026` | Roads & Public Works Operations, Work Orders, Evidence |

> *Note: For production deployments, change these passwords and configure `JWT_SECRET` in `.env`.*

---

## Running Automated Verification Test Suites

JanSakshi includes end-to-end regression test suites verifying security, RBAC, AI fallback, duplicate clustering, and Gmail intent classification:

```bash
cd backend

# 1. Run Master System Audit (Phase 9 - 34 tests)
python test_phase9_master_audit.py

# 2. Run Final Security & Gmail Verification (Concurrency, Rotation, E2E Ingestion)
python test_final_security_and_gmail_verification.py

# 3. Run Gmail Intake Desk Filter Audit (Verifies 100% counter alignment across all 6 tabs)
python test_email_desk_filters.py

# 4. Run Department Inspection & Work Order Workflow
python test_department_inspection_work_orders.py

# 5. Run Roads Department Operational Isolation Test
python test_roads_officer_corrections.py
```

---

## Security & Privacy Commitment

JanSakshi is developed under strict security and data governance standards:
- **Zero Secret Commits:** API keys, OAuth tokens, JWT secrets, and credentials reside exclusively in uncommitted `.env` files.
- **Citizen PII Protection:** Real citizen phone numbers, citizen email records, and sensitive local databases (`*.db`) are strictly excluded from source control.
- **Session Protection:** Dual configurable session lifetime policies (Standard 30-min access token with rotating single-use refresh tokens vs Hackathon Demo mode) backed by server-side `jti` revocation tables.

---

## Academic & Event Attribution

Developed for **CodeForge BuildX 2026**  
**Department of Computer Science & Engineering, Aditya University**  
Academic Year: 2026–2027  
Repository: [https://github.com/tejeswardoolla/JanSakshi](https://github.com/tejeswardoolla/JanSakshi)

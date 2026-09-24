# FoodShare API

FoodShare is a role-based backend REST API that connects restaurants with NGOs to reduce surplus food waste. Restaurants publish surplus food donations, NGOs request pickups, administrators approve and manage accounts, and an intelligent read-only RAG AI assistant helps users navigate guidelines, requirements, and workflows.

## Features

- **JWT Authentication & Security:** OAuth2 password flow with JWT Bearer tokens and Argon2 password hashing.
- **Role-Based Authorization:** Separate access levels and workflows for **Restaurant**, **NGO**, and **Administrator** users.
- **Account Approval Workflow:** Restaurant and NGO signups start in `PENDING` state and require Administrator approval before logging in.
- **Surplus Food Donation Management:** Creation, editing, cancellation, browsing, and area-based filtering for available food donations.
- **Controlled Pickup Lifecycle:** Complete request workflow (request → accept/reject → withdraw → mark collected → confirm completed), with automatic rejection of competing pending requests upon acceptance.
- **Full Audit Traceability:** Comprehensive status history tracking for both donations and pickup requests.
- **Supabase PostgreSQL & Storage:** Hosted PostgreSQL database with private Supabase Storage buckets for user profile images and donation media.
- **Secure Media Handling:** Client-side direct uploads via signed upload URLs and time-limited signed read URLs.
- **RAG AI Assistant Service:** Separately deployable AI microservice providing grounded, read-only guidance on FoodShare business rules, FAQs, and platform usage.

## Tech Stack

- **Core Framework:** FastAPI
- **ORM / Data Models:** SQLModel and SQLAlchemy
- **Database:** PostgreSQL with Psycopg 3 (hosted on Supabase)
- **Object Storage:** Supabase Storage
- **Authentication:** OAuth2 with PyJWT and pwdlib (Argon2)
- **AI / Embeddings:** Google GenAI SDK (Gemini), sentence-transformers (`all-MiniLM-L6-v2`), pgvector
- **Server:** Uvicorn
- **Deployment:** Vercel (Core API) & Render (AI Service via Docker)

## User Roles

| Role | Main Responsibilities |
|---|---|
| **RESTAURANT** | Publish food donations, manage media, review/accept/reject pickup requests, confirm collection completion. |
| **NGO** | Browse available food donations, submit and withdraw pickup requests, confirm food collection. |
| **ADMIN** | Review and approve/reject pending accounts, monitor users, delete inactive accounts. |

Restaurant and NGO registrations begin with `PENDING` approval status. An Administrator must approve the account before the user can log in.

## Workflow & Statuses

```text
Restaurant creates donation (AVAILABLE)
        ↓
NGO submits pickup request (PENDING)
        ↓
Restaurant accepts one request (Donation: RESERVED, Request: ACCEPTED)
   * All other pending requests for this donation are automatically REJECTED *
        ↓
NGO marks pickup collected (Donation: COLLECTED, Request: COLLECTED)
        ↓
Restaurant marks donation completed (Donation: COMPLETED)
```

### Donation Statuses
- `AVAILABLE` → `RESERVED` → `COLLECTED` → `COMPLETED`
- Alternate terminal statuses: `CANCELLED`, `EXPIRED`

### Pickup Request Statuses
- `PENDING` → `ACCEPTED` → `COLLECTED`
- `PENDING` → `REJECTED`
- `PENDING` → `WITHDRAWN`

---

## Installation & Local Setup

### 1. Clone the Repository

```bash
git clone https://github.com/himalaya-pahar/FoodShare.git
cd FoodShare
```

### 2. Create and Activate a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows:

```powershell
venv\Scripts\activate
```

### 3. Install Dependencies

For the core API:

```bash
pip install -r requirements.txt
```

To run or test the AI service locally:

```bash
pip install -r requirements-ai.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root based on `.env.example`:

```env
# Database (PostgreSQL hosted on Supabase)
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/postgres?sslmode=require

# JWT Authentication
SECRET_KEY=replace_with_a_long_random_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Supabase Storage & Credentials
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SECRET_KEY=YOUR_SERVER_ONLY_SUPABASE_SECRET_KEY

# Storage Bucket Names
SUPABASE_PROFILE_IMAGES_BUCKET=profile-images
SUPABASE_DONATION_MEDIA_BUCKET=donation-media

# Startup Database Schema Generation
CREATE_TABLES_ON_STARTUP=false

# AI Assistant Configuration
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=your_gemini_api_key_here
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
AI_CORS_ORIGINS=*
```

> **Warning:** Never commit `.env`, service keys, or database credentials to version control.

### 5. Supabase Setup

1. **Storage Buckets:** In your Supabase dashboard, create two private storage buckets:
   - `profile-images` (allowed: JPEG, PNG, WebP; max size: 5 MB)
   - `donation-media` (allowed: JPEG, PNG, WebP, MP4; max size: 5 MB)

2. **First Database Initialization:**
   For a brand-new database without tables:
   ```env
   CREATE_TABLES_ON_STARTUP=true
   ```
   Start the core API once so SQLModel generates all tables, then revert `CREATE_TABLES_ON_STARTUP=false`.

3. **Administrator Account Setup:**
   FoodShare has no hardcoded admin credentials:
   - Register normally via `POST /signup`.
   - In **Supabase Dashboard → Table Editor → users**, find your account.
   - Update `role = ADMIN` and `approval_status = APPROVED`.
   - You can now log in via `POST /login` with administrator privileges.

### 6. Run the Applications Locally

**Core API (Port 8000):**
```bash
uvicorn main:app --reload --port 8000
```
Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

**AI Assistant Service (Port 8001):**
```bash
# First-time KB indexing
python scripts/reindex_kb.py

# Start AI service
uvicorn ai_service.main:app --reload --port 8001
```
Swagger UI: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

---

## API Endpoints

### Authentication

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/signup` | Public | Register a new Restaurant or NGO account. |
| `POST` | `/login` | Public | Log in with OAuth2 form data (`username` = email, `password`) and receive a JWT. |

### Administration

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/admin/users/pending` | Admin | List pending restaurant and NGO accounts awaiting approval. |
| `PATCH` | `/admin/users/{user_id}/approval` | Admin | Approve or reject a pending account. |
| `GET` | `/admin/users` | Admin | List all registered users. |
| `DELETE` | `/admin/users/{user_id}` | Admin | Delete an inactive non-admin user account. |

### Donations

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/donations/` | Restaurant | Create a new food donation listing. |
| `GET` | `/donations/my` | Restaurant | List donations owned by the current restaurant. |
| `GET` | `/donations/available` | NGO | Browse available food donations (supports `?area=` query). |
| `GET` | `/donations/{donation_id}` | Authenticated | View details of a specific donation. |
| `PATCH` | `/donations/{donation_id}` | Restaurant Owner | Edit details of an available donation. |
| `POST` | `/donations/{donation_id}/cancel` | Restaurant Owner | Cancel an available donation. |

### Pickup Requests

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/donations/{donation_id}/pickup-requests` | NGO | Submit a pickup request for an available donation. |
| `GET` | `/pickup-requests/my` | NGO | List requests submitted by current NGO. |
| `GET` | `/donations/{donation_id}/pickup-requests` | Restaurant Owner | List all pickup requests for a specific donation. |
| `POST` | `/pickup-requests/{request_id}/accept` | Restaurant Owner | Accept request, reserve donation, and reject other requests. |
| `POST` | `/pickup-requests/{request_id}/reject` | Restaurant Owner | Reject a pending pickup request. |
| `POST` | `/pickup-requests/{request_id}/withdraw` | NGO Owner | Withdraw a pending pickup request. |
| `POST` | `/pickup-requests/{request_id}/collect` | NGO Owner | Mark accepted request & donation as collected. |
| `POST` | `/donations/{donation_id}/complete` | Restaurant Owner | Confirm a collected donation as completed. |

### Status & Audit History

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/donations/my/history` | Restaurant | Audit history for all donations owned by current restaurant. |
| `GET` | `/donations/{donation_id}/history` | Owner / Admin | Audit history for a specific donation. |
| `GET` | `/pickup-requests/my/history` | NGO | Audit history for current NGO's pickup requests. |
| `GET` | `/pickup-requests/{request_id}/history` | Owner / Admin | Audit history for a specific pickup request. |

### Profile Image

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/profile-image/upload-url` | Authenticated | Request a temporary signed upload URL for profile photo. |
| `POST` | `/profile-image/{image_id}/complete` | Authenticated | Confirm completion of direct upload. |
| `GET` | `/profile-image/me` | Authenticated | Retrieve temporary signed read URL for current user's photo. |
| `DELETE` | `/profile-image/{image_id}` | Authenticated | Delete current user's profile image. |

### Donation Media

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/donations/{donation_id}/media/upload-url` | Restaurant Owner | Request signed upload URL for donation photo or video. |
| `POST` | `/donation-media/{media_id}/complete` | Restaurant Owner | Confirm completion of media upload. |
| `GET` | `/donations/{donation_id}/media` | Authenticated | List all active media with signed read URLs for a donation. |
| `DELETE` | `/donation-media/{media_id}` | Restaurant Owner | Delete a media item from a donation. |

### User Profile

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/users/me` | Authenticated | Get current authenticated user profile. |

### AI Assistant (Standalone Service)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/health` | Public | Liveness probe for monitoring/load balancing. |
| `POST` | `/ai/chat` | Authenticated | Multi-turn RAG chat answering questions about FoodShare. |

---

## Private Media Upload Flow

Supabase Storage buckets are completely private. Direct uploads and reads follow this sequence:

```text
1. Client calls POST .../upload-url
2. FastAPI registers a PENDING media record in PostgreSQL and returns a signed upload URL
3. Client uploads file directly to Supabase Storage via PUT
4. Client calls POST .../{id}/complete
5. FastAPI verifies existence and marks the record READY
6. Subsequent GET requests dynamically return time-limited signed read URLs
```

---

## Validation & Business Rules

- **Quantities:** Donation food quantity must be strictly greater than zero.
- **Timing:** Pickup deadline must be set after preparation time. NGO estimated pickup time must be before deadline.
- **Concurrency:** An NGO can only submit one active request per donation. Accepting one request automatically sets all competing pending requests to `REJECTED`.
- **Modifications:** Only donations with `AVAILABLE` status may be updated or cancelled.
- **Auditability:** Every workflow status transition is permanently recorded in `status_history`.

---

## Deployment Architecture

FoodShare uses a split deployment model:

```text
┌─────────────────────────┐          ┌─────────────────────────┐
│     Core REST API       │          │   AI Assistant Service  │
│      (FastAPI)          │          │      (FastAPI)          │
│   Deployed on Vercel    │          │    Deployed on Render   │
│   Port: 8000 / HTTPS    │          │    Port: 8001 / HTTPS   │
└────────────┬────────────┘          └────────────┬────────────┘
             │                                    │
             │   Shared Supabase PostgreSQL DB    │
             │   (Users, Donations, Pickups,      │
             │    Status History, ai_chunks)      │
             └──────────────────┬─────────────────┘
                                │
                     ┌──────────┴──────────┐
                     │  Supabase Storage   │
                     │  (Private Buckets)  │
                     └─────────────────────┘
```

1. **Vercel (Core API):** Serves all user authentication, donation management, pickup workflows, and media operations. Ignores commits affecting only AI files via `scripts/vercel-ignore-build.sh`.
2. **Render (AI Service):** Deploys `Dockerfile.ai` as a single-instance container. Builds vector embeddings with sentence-transformers and answers user questions grounded in the knowledge base. Builds trigger only on AI or shared-file changes via `render.yaml` path filters.

For frontend developers integrating the chat interface, refer to [`FRONTEND_INTEGRATION_GUIDE.md`](./FRONTEND_INTEGRATION_GUIDE.md).

## License

This project was developed for academic software engineering purposes.

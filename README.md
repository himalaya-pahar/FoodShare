<<<<<<< HEAD
# FoodShare Backend API

FoodShare is a role-based REST API for coordinating surplus-food donations between restaurants and NGOs. Administrators review accounts, restaurants publish available food, NGOs request collection, and every workflow status change is recorded for traceability.

Built as a software engineering project with FastAPI, SQLModel, SQLite, and JWT authentication.

## Features

- Restaurant, NGO, and administrator roles with role-based authorization.
- Account registration with administrator approval before login.
- JWT Bearer authentication and Argon2 password hashing.
- Donation creation, editing, cancellation, discovery, and area filtering.
- Controlled pickup workflow: request, accept/reject, withdraw, collect, and complete.
- Automatic rejection of competing pending requests when one request is accepted.
- Donation and pickup-request status history for auditability.
- Request validation for food quantity, pickup deadlines, and collection schedules.

## Technology Stack

- **Framework:** FastAPI
- **ORM / database models:** SQLModel and SQLAlchemy
- **Validation:** Pydantic
- **Authentication:** OAuth2 Password flow and JSON Web Tokens (PyJWT)
- **Password hashing:** pwdlib with Argon2
- **Local database:** SQLite
- **Server:** Uvicorn

## Project Structure

```text
FoodShare/
├── main.py                 # FastAPI app and router registration
├── config.py               # Environment-variable configuration
├── database.py             # Engine, session dependency, table creation
├── models.py               # SQLModel database models and enums
├── schemas.py              # Request and response schemas
├── create_admin.py         # Local administrator bootstrap script
├── routers/                # HTTP route definitions
├── repository/             # Business logic and database operations
├── security/               # Hashing, JWT, and authorization dependencies
└── requirements.txt        # Pinned Python dependencies
```

## Roles and Approval

| Role | Main responsibilities |
|---|---|
| **RESTAURANT** | Create and manage donations; review pickup requests; confirm completed collections. |
| **NGO** | Browse available donations; request, withdraw, and mark pickups as collected. |
| **ADMIN** | Review restaurant/NGO accounts; list users; remove inactive accounts. |

Restaurant and NGO signups begin with `PENDING` approval status. An administrator must change the account to `APPROVED` before it can log in. Administrator accounts cannot be created through the public signup endpoint.
=======
# FoodShare API

FoodShare is a role-based backend API that connects restaurants with NGOs to reduce food waste. Restaurants publish surplus food donations, NGOs request pickups, and administrators approve and manage accounts.

## Features

- JWT authentication
- Restaurant, NGO, and Administrator roles
- Account approval workflow
- Food donation management
- Pickup-request workflow
- Donation and pickup status history
- PostgreSQL database hosted on Supabase
- Private Supabase Storage for profile images and donation media
- Signed upload URLs and temporary signed read URLs
- One profile image per user
- Up to five images and one video per donation

## Tech Stack

- FastAPI
- SQLModel / SQLAlchemy
- PostgreSQL with Psycopg
- Supabase PostgreSQL and Storage
- JWT Authentication
- Uvicorn

## User Roles

| Role | Responsibilities |
|---|---|
| Restaurant | Create donations, manage donation media, accept or reject pickup requests |
| NGO | Browse donations, submit pickup requests, confirm collection |
| Administrator | Approve accounts and manage users |
>>>>>>> 0afa05c (integrate Supabase storage and finalize backend setup)

## Workflow

```text
Restaurant creates donation
        ↓
<<<<<<< HEAD
AVAILABLE
        ↓ NGO submits a pickup request
PENDING pickup request
        ↓ Restaurant accepts one request
RESERVED donation + ACCEPTED request
        ↓ NGO confirms collection
COLLECTED donation + COLLECTED request
        ↓ Restaurant confirms completion
COMPLETED donation
```

At acceptance, all other pending requests for that donation are automatically rejected. An available donation can alternatively be cancelled by its restaurant owner.

## Local Setup

### 1. Clone and enter the project
=======
NGO submits pickup request
        ↓
Restaurant accepts one request
        ↓
NGO marks pickup collected
        ↓
Restaurant marks donation completed
```

### Donation Statuses

```text
AVAILABLE → RESERVED → COLLECTED → COMPLETED
```

Other donation statuses:

```text
CANCELLED
EXPIRED
```

### Pickup Request Statuses

```text
PENDING → ACCEPTED → COLLECTED
PENDING → REJECTED
PENDING → WITHDRAWN
```

## Installation
>>>>>>> 0afa05c (integrate Supabase storage and finalize backend setup)

```bash
git clone https://github.com/himalaya-pahar/FoodShare.git
cd FoodShare
<<<<<<< HEAD
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows:

```powershell
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a local `.env` file

Create `.env` in the project root. Do not commit it.

```env
DATABASE_URL=sqlite:///./foodshare.db
SECRET_KEY=replace_with_a_long_random_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Generate a safe local secret with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 5. Start the API
=======

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/postgres?sslmode=require

SECRET_KEY=replace_with_a_long_random_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SECRET_KEY=YOUR_SERVER_ONLY_SUPABASE_SECRET_KEY

SUPABASE_PROFILE_IMAGES_BUCKET=profile-images
SUPABASE_DONATION_MEDIA_BUCKET=donation-media

CREATE_TABLES_ON_STARTUP=false
```

Never commit `.env`, database credentials, JWT secrets, or Supabase secret keys.

## Supabase Setup

Create two private Supabase Storage buckets:

```text
profile-images
donation-media
```

Recommended bucket settings:

| Bucket | Accepted files | Maximum size |
|---|---|---|
| `profile-images` | JPEG, PNG, WebP | 5 MB |
| `donation-media` | JPEG, PNG, WebP, MP4 | 5 MB |

## First Database Setup

For a brand-new database, temporarily set:

```env
CREATE_TABLES_ON_STARTUP=true
```

Run the server once:
>>>>>>> 0afa05c (integrate Supabase storage and finalize backend setup)

```bash
uvicorn main:app --reload
```

<<<<<<< HEAD
The application creates its tables automatically on startup. Open the interactive API documentation at:
=======
After the tables are created, change it back:

```env
CREATE_TABLES_ON_STARTUP=false
```

## Run the API

```bash
uvicorn main:app --reload
```

Open Swagger documentation:
>>>>>>> 0afa05c (integrate Supabase storage and finalize backend setup)

```text
http://127.0.0.1:8000/docs
```

<<<<<<< HEAD
## Initial Administrator

Run the bootstrap script once to create or reuse the local administrator account:

```bash
python create_admin.py
```

Before any public deployment, replace the sample credentials currently in `create_admin.py` with environment-based configuration. Never use example credentials in a real deployment.

## Authentication

### Sign up

`POST /signup` accepts JSON. Use `RESTAURANT` or `NGO` as the role.

```json
{
  "full_name": "Green Plate Restaurant",
  "organization_name": "Green Plate",
  "email": "contact@greenplate.example",
  "password": "strong-password-here",
  "role": "RESTAURANT",
  "phone": "+8801000000000",
  "address": "Dhaka",
  "area": "Dhanmondi"
}
```

### Log in

`POST /login` uses OAuth2 form data, not JSON. Put the email in the `username` field.

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=contact@greenplate.example&password=strong-password-here"
```

Successful login returns an access token. Send it on protected endpoints:

```text
Authorization: Bearer <access_token>
```

## API Endpoints

All endpoints other than signup and login require an approved account and a Bearer token.

### Authentication

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/signup` | Public | Register a restaurant or NGO account. |
| `POST` | `/login` | Public | Log in with OAuth2 form data and receive a JWT. |

### Administration

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/admin/users/pending` | List pending restaurant and NGO accounts. |
| `PATCH` | `/admin/users/{user_id}/approval` | Approve or reject a pending account. |
| `GET` | `/admin/users` | List all users. |
| `DELETE` | `/admin/users/{user_id}` | Delete an inactive non-admin account. |

### Donations

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/donations/` | Restaurant | Create a donation. |
| `GET` | `/donations/my` | Restaurant | List the current restaurant's donations. |
| `GET` | `/donations/available?area={area}` | NGO | Browse available donations; area is optional. |
| `GET` | `/donations/{donation_id}` | Authenticated | View one donation. |
| `PATCH` | `/donations/{donation_id}` | Restaurant owner | Edit an available donation. |
| `POST` | `/donations/{donation_id}/cancel` | Restaurant owner | Cancel an available donation. |

### Pickup Requests

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/donations/{donation_id}/pickup-requests` | NGO | Submit a pickup request. |
| `GET` | `/pickup-requests/my` | NGO | List the current NGO's requests. |
| `GET` | `/donations/{donation_id}/pickup-requests` | Restaurant owner | List requests for one donation. |
| `POST` | `/pickup-requests/{request_id}/accept` | Restaurant owner | Accept one request and reserve the donation. |
| `POST` | `/pickup-requests/{request_id}/reject` | Restaurant owner | Reject a pending request. |
| `POST` | `/pickup-requests/{request_id}/withdraw` | NGO owner | Withdraw a pending request. |
| `POST` | `/pickup-requests/{request_id}/collect` | NGO owner | Mark an accepted request and its donation as collected. |
| `POST` | `/donations/{donation_id}/complete` | Restaurant owner | Confirm a collected donation as completed. |

### Status History

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/donations/my/history` | Restaurant | View history for all owned donations. |
| `GET` | `/donations/{donation_id}/history` | Restaurant owner or Admin | View one donation's history. |
| `GET` | `/pickup-requests/my/history` | NGO | View history for the current NGO's requests. |
| `GET` | `/pickup-requests/{request_id}/history` | NGO owner, Restaurant owner, or Admin | View one pickup request's history. |

## Validation and Data Rules

- Donation quantity must be greater than zero.
- A donation's pickup deadline must be after its preparation time.
- An NGO's estimated pickup time must be after the donation is posted/prepared and before its deadline.
- An NGO can submit only one request per donation.
- Only `AVAILABLE` donations can be edited or cancelled.
- Only one pickup request can be accepted for a donation.
- Workflow state changes are stored in `StatusHistory`.

## Database Models

| Model | Purpose |
|---|---|
| `User` | Restaurant, NGO, and administrator accounts. |
| `Donation` | Food donations posted by restaurants. |
| `PickupRequest` | NGO requests to collect a donation. |
| `StatusHistory` | Audit trail for donation and pickup-request workflow events. |

## Deployment Notes

### Local SQLite

SQLite is the intended local-development database:

```env
DATABASE_URL=sqlite:///./foodshare.db
```

The database file and `.env` are ignored by Git to protect local data and secrets.

### Vercel demonstration deployment

Vercel serverless functions cannot persist a SQLite file in the application directory. For a temporary demonstration only, configure Vercel with:

```env
DATABASE_URL=sqlite:////tmp/foodshare.db
```

Data in `/tmp` may disappear after a cold start, redeploy, or scaling event. Do not use it for real user data.

For a persistent production deployment, move to a managed database and update the database driver/engine configuration accordingly. Also restrict CORS to trusted frontend origins before production use.

## Security Notes

- Keep `.env`, database files, access tokens, and real credentials out of Git.
- Use a long random `SECRET_KEY` and rotate it if it is exposed.
- Use HTTPS in deployed environments.
- Restrict CORS origins for production rather than allowing every origin.
- Move bootstrap administrator credentials out of source code before release.

## License

This repository is an academic software engineering project. Add an explicit license before using it outside the project context.
=======
## Administrator Setup

FoodShare does not contain hardcoded administrator credentials.

1. Create an account normally using `/signup`.
2. Open **Supabase → Table Editor → users**.
3. Find that user.
4. Update:

```text
role = ADMIN
approval_status = APPROVED
```

The user can now log in with their own email and password as an administrator.

## Authentication Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/signup` | Create a new account |
| POST | `/login` | Log in and receive a JWT access token |

`/login` uses OAuth2 form fields:

```text
username = email address
password = password
```

Use the returned access token as a Bearer token for protected endpoints.

## Status History Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/donations/{donation_id}/history` | View donation status history |
| GET | `/pickup-requests/my/history` | View current NGO pickup history |

## Profile Image Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/profile-image/upload-url` | Request a temporary upload URL |
| POST | `/profile-image/{image_id}/complete` | Confirm a completed upload |
| GET | `/profile-image/me` | Get the current user's profile image |
| DELETE | `/profile-image/{image_id}` | Delete the current user's profile image |

Supported profile-image formats:

```text
image/jpeg
image/png
image/webp
```

## Donation Media Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/donations/{donation_id}/media/upload-url` | Request a temporary media upload URL |
| POST | `/donation-media/{media_id}/complete` | Confirm a completed media upload |
| GET | `/donations/{donation_id}/media` | List ready donation media |
| DELETE | `/donation-media/{media_id}` | Delete donation media |

Supported donation-media formats:

```text
image/jpeg
image/png
image/webp
video/mp4
```

## Private Media Upload Flow

Both Supabase Storage buckets are private.

```text
1. Client requests an upload URL from FastAPI
2. FastAPI creates a PENDING media record
3. Client uploads the file directly to Supabase Storage
4. Client calls the complete endpoint
5. FastAPI marks the record READY
6. API returns a temporary signed read URL when media is requested
```

Media does not appear in normal `GET` responses until the upload is completed successfully.

## Deployment Notes

- Configure all environment variables in the hosting provider.
- Keep `CREATE_TABLES_ON_STARTUP=false` after the database schema exists.
- Keep `SUPABASE_SECRET_KEY` server-only.
- Never expose database credentials or Supabase secret keys to a frontend application.

## AI Assistant

The backend ships with a **read-only RAG AI Assistant** mounted at
`POST /ai/chat`. It answers questions about how to use FoodShare and **never**
performs any action that changes application state (no donation creation,
no pickup requests, no account approvals, no status changes).

Brief overview, configuration, and troubleshooting live in
[`ai/README.md`](./ai/README.md). Detailed design + handoff docs are in
[`workspace_ai_implementation/`](./workspace_ai_implementation/).

Quick start:

```bash
pip install -r requirements.txt
# The reindex script below also runs `ai.setup_db.ensure()` first, which
# enables the `vector` extension + creates the `ai_chunks` table for you —
# so no separate `psql` step is needed.
# Note: the embedding model is downloaded the first time it is needed
# (~80 MB, cached in %USERPROFILE%\.cache\huggingface\hub\ on Windows).
python scripts/reindex_kb.py
uvicorn main:app --reload
```

Then open `http://localhost:8000/docs`, authorize with any approved user's
JWT, and try the **AI Assistant → POST /ai/chat** endpoint.

## License

This project was created for academic software-engineering purposes.
>>>>>>> 0afa05c (integrate Supabase storage and finalize backend setup)

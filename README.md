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

## Workflow

```text
Restaurant creates donation
        ↓
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

```bash
git clone https://github.com/himalaya-pahar/FoodShare.git
cd FoodShare
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

```bash
uvicorn main:app --reload
```

The application creates its tables automatically on startup. Open the interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

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

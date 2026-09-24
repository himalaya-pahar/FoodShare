# Functional Requirements

A concise description of what FoodShare does. Use this for high-level
questions such as "what is FoodShare?" and "what does FoodShare support?".

---

## Product purpose

FoodShare is a role-based platform that connects restaurants with NGOs for surplus-food donation coordination. Administrators review accounts, restaurants publish available food, NGOs request collection, and every workflow status change is recorded for traceability.

## User roles

- **RESTAURANT** — creates and manages donations; reviews pickup requests; confirms completed collections.
- **NGO** — browses available donations; requests pickup; withdraws pending requests; marks accepted pickups as collected.
- **ADMIN** — reviews pending accounts; approves or rejects them; lists all users; deletes inactive non-admin accounts.

Admin accounts cannot be created through the public signup endpoint — they are bootstrapped out-of-band.

## Authentication

- OAuth2 password flow with JWT.
- Email and password are required at signup.
- Login requires `APPROVED` status.
- Passwords are stored using Argon2 hashing (via `pwdlib`).

## Account registration

- New restaurant / NGO accounts start in `PENDING` status.
- An admin must change the status to `APPROVED` before the user can log in.
- An admin can also change the status to `REJECTED`.

## Donation management

- Restaurants can create, edit, and cancel donations.
- Only `AVAILABLE` donations can be edited or cancelled.
- Each donation has food name, description, quantity (with unit), prepared-at time, pickup deadline, pickup area, pickup address, storage notes, and allergen info.
- Donations can have up to 5 images and 1 video attached.

## Browse

- NGOs can browse donations currently in `AVAILABLE` status.
- The browse list can be filtered by area.

## Pickup-request workflow

- An NGO submits a pickup request against an available donation.
- Each NGO can submit at most one request per donation.
- The restaurant reviews pending requests and chooses to accept or reject one.
- When one request is accepted, all other pending requests for that donation are automatically rejected.
- The NGO can withdraw a pending request.
- The NGO marks the request as collected after physical pickup.
- The restaurant confirms completion.

## State tracking

- Every donation and pickup-request status change is recorded with old status, new status, actor, optional note, and timestamp.
- History is read-only and append-only through the API.

## Media handling

- Profile images (one per user) and donation media are stored in private Supabase buckets.
- Uploads use signed upload URLs returned by the API.
- Reading uses temporary signed URLs.
- Maximum file size: 5 MB. Accepted types: JPEG, PNG, WebP for images; MP4 for video (donation media only).

## Authorization rules (summary)

| Action | Who can do it |
|---|---|
| Sign up | Anyone (role must be RESTAURANT or NGO) |
| Log in | Approved users only |
| Create / edit / cancel an available donation | Restaurant owner |
| Browse available donations | NGO |
| Request pickup on a donation | NGO |
| Withdraw own pending pickup request | NGO |
| Mark accepted request as collected | NGO owner of the request |
| Accept or reject a pending request | Restaurant owner of the donation |
| Confirm a donation as completed | Restaurant owner |
| Approve / reject accounts | Admin |
| Delete an inactive non-admin user | Admin |
| Read status history | Restaurant (own), NGO (own), Admin (any) |

## Non-functional requirements (as documented)

- The system must remain usable if the AI assistant is unavailable (the AI is an auxiliary module).
- API keys must be stored as environment variables and must not be committed to version control.
- Passwords must never be stored in plain text.
- All role-restricted endpoints must reject unauthorized requests with `401` or `403`.
- The state machine must be enforced server-side; the client cannot bypass it.
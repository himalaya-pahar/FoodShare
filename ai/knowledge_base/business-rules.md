# Business Rules

This document defines the **rules** FoodShare enforces. Use these facts for
"can I...?" and "what happens if...?" questions. If a rule is not stated
here, explain that the available information does not specify it.

---

## Accounts

- New accounts can only be created with role `RESTAURANT` or `NGO`. Attempting to sign up with role `ADMIN` is rejected.
- A new restaurant or NGO account starts in `PENDING` approval status and **cannot log in** until an admin changes it to `APPROVED`.
- An admin can `APPROVE` or `REJECT` a pending account.
- An admin can `DELETE` any non-admin user account that is inactive.
- An account with role `ADMIN` does not go through the approval gate; admins are bootstrapped out-of-band.
- Login is OAuth2-form style: the email goes in the `username` field; the password is sent as form data, not JSON.

## Validation rules (enforced by the API)

These rules are checked by the API. The AI must not invent new rules.

- A donation's **quantity must be greater than zero**.
- A donation's **pickup deadline must be strictly after its prepared-at time**.
- A pickup request's **estimated pickup time must be after the donation is prepared and before its pickup deadline**.
- **An NGO can submit at most one pickup request per donation.**
- A donation can be edited only while its status is `AVAILABLE`.
- A donation can be cancelled only while its status is `AVAILABLE`.
- A donation can be completed only after the NGO has marked it `COLLECTED`.

## Donation state machine

```
AVAILABLE  ── NGO requests pickup ──►  AVAILABLE  (request: PENDING)
AVAILABLE  ── restaurant accepts one request ──►  RESERVED  (request: ACCEPTED)
RESERVED   ── NGO marks pickup collected ──►  COLLECTED  (request: COLLECTED)
COLLECTED  ── restaurant confirms ──►  COMPLETED
AVAILABLE  ── restaurant cancels ──►  CANCELLED
AVAILABLE  ── deadline passes (system action) ──►  EXPIRED
```

Other transitions are not allowed.

## Pickup-request state machine

```
PENDING  ── restaurant accepts  ──►  ACCEPTED
PENDING  ── restaurant rejects  ──►  REJECTED
PENDING  ── NGO withdraws        ──►  WITHDRAWN
ACCEPTED ── NGO marks collected  ──►  COLLECTED
```

Other transitions are not allowed.

## Acceptance side-effect (important)

When a restaurant accepts **one** pending pickup request for a donation:

- the donation becomes `RESERVED`,
- the accepted request becomes `ACCEPTED`,
- **every other pending request for the same donation is automatically `REJECTED`**.

This is enforced server-side. The restaurant does not have to reject them manually.

## Status history

- Every change to a donation status or pickup-request status is recorded in the `status_history` table with: actor (user id), old status, new status, optional note, timestamp.
- History is append-only and cannot be edited or deleted through the API.

## Media (profile images and donation media)

- Both `profile-images` and `donation-media` Supabase storage buckets are **private**.
- Upload flow has three steps: (1) client requests a signed upload URL from the API, (2) client uploads directly to Supabase Storage, (3) client calls a `complete` endpoint so the API flips the record from `PENDING` → `READY`.
- Media that is still `PENDING` does not appear in normal `GET` responses.
- Reading media returns a **temporary signed URL**, not the raw bucket URL.
- A user can have **at most one** profile image at a time.
- A donation can have **up to 5 images and 1 video**.
- Accepted content types:
  - profile image: `image/jpeg`, `image/png`, `image/webp`
  - donation media: `image/jpeg`, `image/png`, `image/webp`, `video/mp4`
- Maximum file size on both buckets is **5 MB**.

## Authentication

- Authentication is OAuth2 password flow using JWT.
- Tokens are signed with the `SECRET_KEY` and `ALGORITHM` (`HS256` by default).
- Default token lifetime is configured by `ACCESS_TOKEN_EXPIRE_MINUTES` (60 by default).
- Passwords are hashed with Argon2 via the `pwdlib` library. Plain-text passwords are never stored.

## Roles and access summary

| Role | Can do |
|---|---|
| Any logged-in approved user | view a single donation; view donation or pickup-request history (subject to ownership rules) |
| Restaurant | create / edit / cancel `AVAILABLE` donations; list own donations; list requests on own donations; accept or reject requests; confirm completion |
| NGO | browse `AVAILABLE` donations with optional area filter; submit a pickup request; withdraw own pending request; mark an accepted request as collected |
| Admin | list pending users; approve / reject them; list all users; delete inactive non-admin users; view any donation history |

## What the AI must not do

Even when the AI knows the answer, it must not:

- create donations
- request pickups
- approve or reject accounts
- change donation or pickup-request status
- upload or delete media
- bypass the admin approval gate
- promise to perform a future action ("I will approve your account")

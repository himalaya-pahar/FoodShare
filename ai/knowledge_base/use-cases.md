# Use Cases

End-to-end scenarios for FoodShare, mapped to the actual API endpoints. Use this when a user asks "what should I do?" in narrative form.

> Source: requirements PDF §3, cross-checked against `routers/*.py`.

---

## UC-1 — Restaurant posts a new donation

**Actor:** Restaurant (status: `APPROVED`)
**Trigger:** Surplus food available.
**Pre-condition:** Restaurant is logged in.

**Flow:**
1. Restaurant submits a donation via `POST /donations/`.
2. Server validates: quantity > 0; pickup deadline > prepared_at.
3. Server creates the donation with status `AVAILABLE`.
4. Status history record created: action = `CREATE`.

**Result:** Donation appears in NGO browse results.

**Endpoint:** `POST /donations/` (Restaurant only)

---

## UC-2 — NGO browses available donations

**Actor:** NGO
**Trigger:** NGO wants to find food to pick up.
**Pre-condition:** NGO is logged in.

**Flow:**
1. NGO requests `GET /donations/available?area={area}` (area is optional).
2. Server returns donations in status `AVAILABLE` whose `pickup_area` matches (when area is supplied).
3. NGO opens a donation via `GET /donations/{donation_id}` to see full details.

**Result:** NGO sees a list with key facts (name, quantity, deadline, area).

**Endpoints:** `GET /donations/available`, `GET /donations/{id}`

---

## UC-3 — NGO submits a pickup request

**Actor:** NGO
**Trigger:** NGO wants to claim a specific donation.
**Pre-condition:** NGO is logged in, donation is `AVAILABLE`, NGO has no existing request on it.

**Flow:**
1. NGO calls `POST /donations/{donation_id}/pickup-requests` with `estimated_pickup_at` and optional `message`.
2. Server validates: estimated time is between `prepared_at` and `pickup_deadline` (inclusive of prepared, exclusive of deadline, depending on implementation).
3. Server rejects if the NGO already has a request for this donation (uniqueness constraint).
4. On success, request is created with status `PENDING` and a status history entry is written.

**Result:** Restaurant sees the new pending request on the donation.

**Endpoint:** `POST /donations/{donation_id}/pickup-requests` (NGO only)

---

## UC-4 — Restaurant reviews pending pickup requests

**Actor:** Restaurant
**Trigger:** At least one pickup request exists on one of the restaurant's donations.

**Flow:**
1. Restaurant calls `GET /donations/{donation_id}/pickup-requests` to list requests for one donation.
2. Or `GET /donations/my` then drill in.
3. For each `PENDING` request, restaurant decides.

**Result:** Restaurant sees who wants what, when.

**Endpoints:** `GET /donations/{donation_id}/pickup-requests`, `GET /donations/my`

---

## UC-5 — Restaurant accepts a request

**Actor:** Restaurant
**Trigger:** Restaurant decides to grant one NGO the pickup.
**Pre-condition:** The donation is `AVAILABLE`. The request is `PENDING`.

**Flow:**
1. Restaurant calls `POST /pickup-requests/{request_id}/accept`.
2. Server flips the request to `ACCEPTED`.
3. Server flips the donation to `RESERVED`.
4. Server flips **every other** `PENDING` request on the same donation to `REJECTED`.
5. Each status change writes a history entry.

**Result:** Only the accepted NGO may now proceed; the others see their request as `REJECTED`.

**Endpoint:** `POST /pickup-requests/{request_id}/accept` (Restaurant owner)

---

## UC-6 — Restaurant rejects a request

**Actor:** Restaurant
**Trigger:** Restaurant does not want to grant a specific NGO.
**Pre-condition:** The request is `PENDING`.

**Flow:**
1. Restaurant calls `POST /pickup-requests/{request_id}/reject`.
2. Server flips the request to `REJECTED` and writes a history entry.

**Result:** NGO sees their request as `REJECTED`. The donation stays `AVAILABLE` for other requests.

**Endpoint:** `POST /pickup-requests/{request_id}/reject`

---

## UC-7 — NGO withdraws a request

**Actor:** NGO
**Trigger:** NGO changes their mind before the restaurant decides.
**Pre-condition:** The request is `PENDING` and owned by the NGO.

**Flow:**
1. NGO calls `POST /pickup-requests/{request_id}/withdraw`.
2. Server flips the request to `WITHDRAWN` and writes a history entry.

**Result:** The donation stays `AVAILABLE` for other NGOs (or stays as it was).

**Endpoint:** `POST /pickup-requests/{request_id}/withdraw`

---

## UC-8 — NGO collects the food

**Actor:** NGO
**Trigger:** NGO has physically picked up the donation.
**Pre-condition:** The request is `ACCEPTED` and the donation is `RESERVED`.

**Flow:**
1. NGO calls `POST /pickup-requests/{request_id}/collect`.
2. Server flips the request to `COLLECTED`.
3. Server flips the donation to `COLLECTED`.
4. History entries written.

**Result:** Restaurant is notified; donation is now waiting for the restaurant to confirm completion.

**Endpoint:** `POST /pickup-requests/{request_id}/collect`

---

## UC-9 — Restaurant confirms completion

**Actor:** Restaurant
**Trigger:** Restaurant has verified the food was handed off.
**Pre-condition:** The donation is `COLLECTED`.

**Flow:**
1. Restaurant calls `POST /donations/{donation_id}/complete`.
2. Server flips the donation to `COMPLETED`.
3. History entry written.

**Result:** Donation lifecycle ends.

**Endpoint:** `POST /donations/{donation_id}/complete`

---

## UC-10 — Restaurant cancels an available donation

**Actor:** Restaurant
**Trigger:** Restaurant no longer wants to give away a donation they posted.
**Pre-condition:** The donation is `AVAILABLE`.

**Flow:**
1. Restaurant calls `POST /donations/{donation_id}/cancel`.
2. Server flips the donation to `CANCELLED`.
3. Any `PENDING` pickup requests on this donation are automatically `REJECTED` (the food is no longer available).
4. History entries written.

**Result:** Donation disappears from NGO browse results; pending requests become `REJECTED`.

**Endpoint:** `POST /donations/{donation_id}/cancel`

---

## UC-11 — Admin approves a pending account

**Actor:** Admin
**Trigger:** A restaurant or NGO has signed up.
**Pre-condition:** Account is in status `PENDING`.

**Flow:**
1. Admin calls `GET /admin/users/pending`.
2. Admin reviews the listing.
3. Admin calls `PATCH /admin/users/{user_id}/approval` with `{ "approval_status": "APPROVED" }` (or `REJECTED`).

**Result:** The user can now log in (if approved). On rejection, they cannot.

**Endpoints:** `GET /admin/users/pending`, `PATCH /admin/users/{user_id}/approval`

---

## UC-12 — User inspects status history

**Actors:** Restaurant (own donations), NGO (own requests), Admin (any donation).
**Trigger:** User wants an audit trail.

**Flow:**
1. Restaurant: `GET /donations/{donation_id}/history` or `GET /donations/my/history`.
2. NGO: `GET /pickup-requests/{request_id}/history` or `GET /pickup-requests/my/history`.
3. Admin: same restaurant endpoint on any donation.

**Result:** List of every status change with actor, old/new status, optional note, timestamp.

**Endpoints:** `GET /donations/{id}/history`, `GET /donations/my/history`, `GET /pickup-requests/{id}/history`, `GET /pickup-requests/my/history`

---

## UC-13 — User updates profile image

**Actor:** Any approved user.
**Pre-condition:** Logged in.

**Flow:**
1. Client requests `POST /profile-image/upload-url` (with `content_type`).
2. Server returns a signed upload URL and a media record in `PENDING`.
3. Client uploads the file directly to Supabase Storage.
4. Client calls `POST /profile-image/{image_id}/complete`.
5. Server flips the record to `READY`.

**Result:** Future calls to `GET /profile-image/me` return a temporary signed read URL.

**Endpoints:** `POST /profile-image/upload-url`, `POST /profile-image/{id}/complete`, `GET /profile-image/me`, `DELETE /profile-image/{id}`

---

## UC-14 — Restaurant attaches photos / a video to a donation

**Actor:** Restaurant (donation owner).
**Trigger:** Restaurant wants NGOs to see the food.

**Flow:**
1. Client requests `POST /donations/{donation_id}/media/upload-url` (with `content_type` and `media_type`).
2. Server returns a signed upload URL and a media record.
3. Client uploads to Supabase Storage.
4. Client calls `POST /donation-media/{media_id}/complete`.
5. Server flips the record to `READY`.

**Result:** Media appears in `GET /donations/{donation_id}/media` and is served to NGOs as temporary signed URLs.

**Endpoints:** `POST /donations/{id}/media/upload-url`, `POST /donation-media/{id}/complete`, `GET /donations/{id}/media`, `DELETE /donation-media/{id}`

---

## Error scenarios the AI should be aware of

- **Validation failure** (e.g. quantity ≤ 0, deadline ≤ prepared_at, estimated pickup time outside window) → `400` with a clear message.
- **Uniqueness failure** (NGO already requested this donation) → `400` "duplicate pickup request".
- **State-machine violation** (e.g. trying to accept an already-`REJECTED` request, trying to edit a `RESERVED` donation) → `400` or `409` depending on the route.
- **Forbidden** (NGO tries to access a restaurant endpoint) → `403`.
- **Unauthorized** (no / invalid token) → `401`.
- **Not found** (donation / request id doesn't exist or belongs to another user) → `404`.
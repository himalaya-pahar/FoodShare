# User Guide

This is a plain-English walkthrough of **how to use FoodShare**, role by role. The AI assistant cites this file when answering "how do I…" questions.

> Source: requirements PDF §3.

---

## For everyone

### I don't have an account yet

1. Open the FoodShare mobile app.
2. Tap **Sign up**.
3. Choose your role: **Restaurant** or **NGO** (you cannot sign up as Admin).
4. Provide your full name, organization name (optional), email, password, phone (optional), address (optional), and the local **area** you operate in (e.g. "Dhanmondi").
5. Submit.
6. Your account is now **`PENDING`**. You cannot log in yet.

### I'm waiting to be approved

An administrator reviews pending accounts. When your status becomes **`APPROVED`**, you can log in. Until then, login attempts will return "Your account is pending admin approval."

### Logging in

1. Open the app.
2. Tap **Login**.
3. Enter your email in the **username** field and your password.
4. Submit.

A successful login returns a JWT access token. The app stores it and sends it on every protected request as `Authorization: Bearer <token>`.

### Common errors

| You see | Meaning |
|---|---|
| `Incorrect email or password` | Wrong credentials. Try again or use password reset (if available). |
| `Your account is pending admin approval` | Your account hasn't been approved yet. Wait for an admin. |
| `Email already registered` | Someone signed up with that email already. Try logging in, or use a different email. |
| `Admin accounts cannot be created through signup` | Admin accounts can't be self-registered; they're created separately. |

---

## For restaurants

### Posting a new donation

1. Log in as a Restaurant.
2. Go to **My Donations** → **Create Donation**.
3. Fill in:
   - **Food name** (short label, e.g. "Cooked rice and curry")
   - **Description** (optional, more detail)
   - **Quantity** (a positive number) and **Unit** (e.g. "kg", "packets", "litres")
   - **Prepared at** (when the food was cooked or packaged — must be earlier than now)
   - **Pickup deadline** (when the food stops being safe to collect — must be **after** `prepared_at`)
   - **Pickup area** (e.g. "Dhanmondi") and **Pickup address**
   - **Storage notes** (e.g. "Keep refrigerated") — optional
   - **Allergen info** (e.g. "Contains peanuts") — optional
4. Submit. The donation starts in status `AVAILABLE` and is visible to NGOs.

### Editing or cancelling a donation

- You can edit an `AVAILABLE` donation — for example, to update the quantity or push the deadline back.
- You can cancel an `AVAILABLE` donation (it moves to `CANCELLED`). Once it is no longer `AVAILABLE`, you cannot edit or cancel it.
- You cannot un-cancel a donation. The system does not currently support re-opening.

### Reviewing pickup requests

1. Go to **My Donations**.
2. Open a donation and view the list of requests below it.
3. For each `PENDING` request you can **Accept** or **Reject**.
4. When you accept one, the donation becomes `RESERVED` and all other pending requests for it are **automatically rejected**.

### Confirming collection

1. After the NGO marks the request `COLLECTED`, the donation becomes `COLLECTED`.
2. From the donation page, tap **Mark Completed** to confirm the donation is fully handed off. Status moves to `COMPLETED`.

### Profile image and donation photos / video

- **Profile image:** open **Profile → Edit photo**, choose an image (JPEG / PNG / WebP, up to 5 MB). The upload has three steps: get signed URL → upload → confirm.
- **Donation media:** on a donation page, add up to **5 images and 1 video** (JPEG / PNG / WebP / MP4). Each upload goes through the same three-step flow. Media marked `READY` is shown to NGOs; `PENDING` uploads are not visible until confirmed.

---

## For NGOs

### Browsing donations

1. Log in as an NGO.
2. Go to **Browse**.
3. The list is filtered to donations in status `AVAILABLE`.
4. Optionally filter by **area** (e.g. "Mirpur"). The filter matches the donation's `pickup_area`.

### Viewing one donation

Tap a card. You can see:
- The food name, description, quantity, unit.
- When it was prepared and when the pickup deadline expires.
- Pickup area and address.
- Storage and allergen info (if the restaurant provided them).
- Photos and a video (if any have been uploaded and confirmed).

### Requesting a pickup

1. Open an available donation.
2. Tap **Request pickup**.
3. Enter your **estimated pickup time**. The system will reject your request if the time is **before** the donation's `prepared_at` or **after** the `pickup_deadline`.
4. Optionally include a short **message** for the restaurant.
5. Submit. Your request is now `PENDING`.

You can have at most **one** request per donation. If you already submitted one, the button will not appear again.

### Withdrawing a request

You can withdraw a `PENDING` request. Once a request becomes `ACCEPTED`, only the restaurant can change it.

### After the restaurant accepts

When the restaurant accepts your request:
- The donation becomes `RESERVED`.
- Any other NGO's pending request for the same donation is auto-rejected.
- You will see your request as `ACCEPTED`.

### Confirming collection

When you physically pick up the food, open the request and tap **Mark Collected**.
- The pickup-request status becomes `COLLECTED`.
- The donation becomes `COLLECTED`.
- The restaurant then reviews and confirms with **Mark Completed**.

### My history

**My Pickup History** lists every status change across all your requests with timestamps.

---

## For administrators

### Reviewing pending accounts

1. Log in as Admin.
2. Go to **Pending Users**.
3. For each pending account you see the email, role, full name, organization, area, and when they signed up.
4. Click **Approve** or **Reject** on the account.

### Listing all users

**All Users** shows every account, including approved, rejected, and admin users. Search by name or email.

### Deleting a user

You can delete any **inactive non-admin** user. Deletion is permanent and the API will not undo it.

### Donation history (audit)

For any donation, you can see the full status timeline — when it was posted, when pickup was requested, accepted, collected, completed, or cancelled. The same exists for pickup requests.

### What you cannot do

- You cannot sign up another admin from the public signup endpoint. Admin accounts are bootstrapped out-of-band.
- You cannot edit a donation's history. The history is append-only.

---

## Status cheat-sheet

| Status | Meaning (donation) | Meaning (pickup request) |
|---|---|---|
| `AVAILABLE` / `PENDING` | Open for NGOs to request | Waiting for restaurant decision |
| `RESERVED` / `ACCEPTED` | Restaurant accepted one NGO | The accepted request |
| `COLLECTED` / `COLLECTED` | NGO has picked up the food | NGO has marked pickup done |
| `COMPLETED` | Restaurant confirmed the handoff | — |
| `REJECTED` | — | Restaurant said no |
| `WITHDRAWN` | — | NGO withdrew before acceptance |
| `CANCELLED` | Restaurant cancelled | — |
| `EXPIRED` | Pickup deadline passed | — |

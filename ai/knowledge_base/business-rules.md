# FoodShare Rules

Use these user-facing rules when explaining what people can do in FoodShare. Do not discuss implementation details or private technical information.

## Accounts

- People can register as a Restaurant or NGO.
- A new account waits for administrator approval before it can be used to log in.
- Administrators review accounts and can approve or reject them.
- Administrator accounts are managed separately and cannot be created through normal sign-up.

## Donations

- Restaurants create donations for surplus food.
- A donation needs a positive quantity, a prepared time, a pickup deadline, a pickup area, and an address.
- The pickup deadline must be later than the prepared time.
- A restaurant can edit or cancel a donation only while it is Available.
- A donation cannot be reopened after it is cancelled.

## Pickup requests

- NGOs can request a pickup only for an Available donation.
- An NGO can make only one request for a particular donation.
- The estimated pickup time must fit within the donation's pickup window.
- A restaurant can accept or reject pending requests.
- When one request is accepted, other pending requests for that donation are rejected automatically.
- An NGO can withdraw its own pending request.

## Statuses

- Available: open for NGO pickup requests.
- Reserved: a restaurant accepted one NGO's request.
- Collected: the NGO marked the food as picked up.
- Completed: the restaurant confirmed the handoff.
- Cancelled: the restaurant cancelled an Available donation.
- Expired: the pickup deadline passed.

## Handoff

- An NGO marks an accepted pickup as Collected after physically receiving the food.
- The restaurant confirms the handoff by marking the donation Completed.
- Status history is view-only and records changes for accountability.

## Assistant limits

The assistant explains FoodShare and cannot create donations, request pickups, approve accounts, change statuses, upload files, or perform any other action.

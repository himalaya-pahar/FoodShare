# Frequently Asked Questions

Short Q&A pairs distilled from the FoodShare requirements. The AI assistant cites these when a user's question matches an existing FAQ.

> Source: requirements PDF and FoodShare code. No external facts.

---

**Q: I just signed up. Why can't I log in?**
A: New restaurant and NGO accounts are placed in `PENDING` status by the API. An administrator has to change the status to `APPROVED` before you can log in. Wait for the admin to review your account.

**Q: How do I sign up as an admin?**
A: You cannot. The signup endpoint rejects role `ADMIN`. Admin accounts are created out-of-band by the project owner.

**Q: How does an NGO request a pickup?**
A: An approved NGO opens an `AVAILABLE` donation, taps **Request pickup**, provides an estimated pickup time that falls between the donation's prepared-at time and its pickup deadline, optionally adds a short message, and submits. The request is created with status `PENDING`.

**Q: What happens after I submit a pickup request?**
A: Your request sits as `PENDING`. The restaurant that posted the donation reviews it and either accepts or rejects it. If they accept a different request first, yours is automatically rejected.

**Q: What does "Available" mean?**
A: The donation has been posted by a restaurant and is open for NGOs to request. Available donations can still be edited or cancelled by the restaurant owner.

**Q: What does "Reserved" mean?**
A: The restaurant has accepted one NGO's pickup request. The donation is no longer available for other NGOs, and that NGO can proceed to collect the food.

**Q: What does "Collected" mean?**
A: The NGO has marked the pickup as collected. At this point the donation is waiting for the restaurant to confirm completion.

**Q: What does "Completed" mean?**
A: The restaurant has confirmed that the food was successfully handed off. The donation's lifecycle is finished.

**Q: Can a restaurant edit a donation after it's been accepted by an NGO?**
A: No. Only `AVAILABLE` donations can be edited or cancelled. Once a donation moves to `RESERVED`, its details are frozen until the workflow ends.

**Q: Can an NGO submit two pickup requests on the same donation?**
A: No. The server enforces one request per (NGO, donation) pair. If you have already requested it, the request button won't appear again.

**Q: Can an admin change their mind on a rejection?**
A: Yes — the admin endpoint accepts any approval-status update (`APPROVED` or `REJECTED`) on a user.

**Q: What file types can I attach to a donation?**
A: Up to 5 images in JPEG, PNG, or WebP, and 1 video in MP4. Each file can be at most 5 MB.

**Q: How big can my profile image be?**
A: Up to 5 MB. Accepted types: JPEG, PNG, WebP.

**Q: Are the uploaded files public?**
A: No. Both `profile-images` and `donation-media` buckets are private. Files are uploaded using signed upload URLs and read using temporary signed URLs returned by the API.

**Q: Can I see who acted on a donation — and when?**
A: Yes. Status history endpoints return every status change with the actor (user id), old status, new status, optional note, and timestamp.

**Q: Can I delete my account?**
A: There is no self-service delete endpoint. An admin can delete an inactive non-admin user.

**Q: Can the AI assistant create a donation or request a pickup for me?**
A: No. The AI assistant is informational only. It can explain how the system works and what each step does, but it does not perform any action that changes the state of the application.

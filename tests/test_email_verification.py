"""
Comprehensive test suite for the Email Verification + Admin Approval flow.

Tests:
1. Complete happy path: Signup -> pending_email -> verify token -> pending_admin -> admin approve -> active -> access protected API
2. Rejection flow: Admin reject -> rejected -> access blocked
3. Verification token edge cases:
   - Invalid token
   - Reused token (token invalidated after first use)
   - Missing token
4. Access control while in different statuses:
   - pending_email cannot login or access protected API
   - pending_admin cannot login or access protected API
   - rejected cannot login or access protected API
   - active user CAN login and access protected API
5. Resend verification flow:
   - Resend for pending_email generates new token and invalidates old token
   - Resend rate limiting / cooldown enforcement
   - Resend for already verified / active user rejected
   - Resend for non-existent user returns 404
   - Resend for rejected user rejected
6. Admin approval edge cases:
   - Unauthorized (anonymous) approval rejected
   - Normal (non-admin) user attempting approval rejected
   - Admin approving already active user rejected
   - Admin approving user before email verification rejected
   - Admin rejecting already rejected user rejected
7. Signup edge cases:
   - Duplicate email rejected
   - Admin account signup forbidden
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import database as d_b
from main import app
from models import (
    ApprovalStatus,
    User,
    UserRole,
    UserStatus,
    utc_now,
)
from schemas import (
    ApprovalUpdate,
    ResendVerificationRequest,
    UserSignup,
)
from security import hashing, token
from security.verification import hash_verification_token
from services.email import email_service


class TestEmailVerificationAndAdminApproval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite test engine with StaticPool
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(cls.test_engine)

        def get_test_session():
            with Session(cls.test_engine) as session:
                yield session

        app.dependency_overrides[d_b.get_session] = get_test_session
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def setUp(self):
        # Clear tables between tests
        with Session(self.test_engine) as session:
            session.exec(User.__table__.delete())
            session.commit()

        # Captured emails list
        self.sent_emails = []

        def mock_send(to_email, full_name, raw_token, request_base_url=None):
            self.sent_emails.append({
                "to_email": to_email,
                "full_name": full_name,
                "raw_token": raw_token,
                "request_base_url": request_base_url,
            })
            return True

        self.email_patcher = patch.object(
            email_service,
            "send_verification_email",
            side_effect=mock_send,
        )
        self.email_patcher.start()

    def tearDown(self):
        self.email_patcher.stop()

    def _create_admin_user(self, email="admin@foodshare.test", password="adminpassword123") -> User:
        """Helper to create an active admin user."""
        with Session(self.test_engine) as session:
            admin = User(
                full_name="System Administrator",
                organization_name="FoodShare Admin",
                email=email,
                password_hash=hashing.get_hash_password(password),
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                email_verified=True,
                email_verified_at=utc_now(),
                approval_status=ApprovalStatus.APPROVED,
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
            return admin

    def _get_admin_token(self, email="admin@foodshare.test", password="adminpassword123") -> str:
        """Helper to get a JWT token for the admin user."""
        response = self.client.post(
            "/login",
            data={"username": email, "password": password},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    # --------------------------------------------------------------------------
    # 1. Full Happy Path Flow
    # --------------------------------------------------------------------------
    def test_complete_verification_and_approval_flow(self):
        # Setup Admin
        self._create_admin_user()
        admin_token = self._get_admin_token()

        # Step 1: User Signup
        signup_payload = {
            "full_name": "Green Bistro",
            "organization_name": "Green Bistro LLC",
            "email": "contact@greenbistro.test",
            "password": "SecurePassword123!",
            "role": "RESTAURANT",
            "phone": "+1234567890",
            "address": "123 Food Street",
            "area": "Downtown",
        }
        res_signup = self.client.post("/auth/signup", json=signup_payload)
        self.assertEqual(res_signup.status_code, 201)
        signup_data = res_signup.json()

        # Verify initial status is pending_email
        self.assertEqual(signup_data["status"], "pending_email")
        self.assertFalse(signup_data["email_verified"])
        self.assertNotIn("verification_token", signup_data)
        self.assertNotIn("verification_token_hash", signup_data)

        # Verify email was sent and contains raw token
        self.assertEqual(len(self.sent_emails), 1)
        raw_token = self.sent_emails[0]["raw_token"]
        self.assertEqual(self.sent_emails[0]["to_email"], "contact@greenbistro.test")
        self.assertTrue(len(raw_token) > 20)

        # Verify DB contains only hash, not raw token
        with Session(self.test_engine) as session:
            db_user = session.exec(
                select(User).where(User.email == "contact@greenbistro.test")
            ).first()
            self.assertIsNotNone(db_user)
            self.assertEqual(db_user.status, UserStatus.PENDING_EMAIL)
            self.assertFalse(db_user.email_verified)
            self.assertNotEqual(db_user.verification_token_hash, raw_token)
            self.assertEqual(db_user.verification_token_hash, hash_verification_token(raw_token))

        # Step 2: Attempt Login while pending_email -> Must be Forbidden
        res_login_pending = self.client.post(
            "/login",
            data={"username": "contact@greenbistro.test", "password": "SecurePassword123!"},
        )
        self.assertEqual(res_login_pending.status_code, 403)
        self.assertIn("not verified", res_login_pending.json()["detail"].lower())

        # Step 3: User Clicks Verification Link -> GET /auth/verify-email?token=<raw_token>
        res_verify = self.client.get(f"/auth/verify-email?token={raw_token}")
        self.assertEqual(res_verify.status_code, 200)
        verify_data = res_verify.json()
        self.assertTrue(verify_data["email_verified"])
        self.assertEqual(verify_data["status"], "pending_admin")

        # Verify DB updated and token invalidated (single-use)
        with Session(self.test_engine) as session:
            db_user = session.exec(
                select(User).where(User.email == "contact@greenbistro.test")
            ).first()
            self.assertEqual(db_user.status, UserStatus.PENDING_ADMIN)
            self.assertTrue(db_user.email_verified)
            self.assertIsNotNone(db_user.email_verified_at)
            self.assertIsNone(db_user.verification_token_hash)  # Invalidation check!
            user_id = db_user.id

        # Step 4: Attempt Login while pending_admin -> Must be Forbidden
        res_login_admin_pending = self.client.post(
            "/login",
            data={"username": "contact@greenbistro.test", "password": "SecurePassword123!"},
        )
        self.assertEqual(res_login_admin_pending.status_code, 403)
        self.assertIn("pending admin approval", res_login_admin_pending.json()["detail"].lower())

        # Step 5: Admin Lists Pending Users
        res_pending_list = self.client.get(
            "/admin/users/pending",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res_pending_list.status_code, 200)
        pending_items = res_pending_list.json()["items"]
        self.assertTrue(any(u["id"] == user_id for u in pending_items))

        # Step 6: Admin Approves User -> PATCH /admin/users/{user_id}/approve
        res_approve = self.client.patch(
            f"/admin/users/{user_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res_approve.status_code, 200)
        approved_data = res_approve.json()
        self.assertEqual(approved_data["status"], "active")
        self.assertEqual(approved_data["approval_status"], "APPROVED")

        # Step 7: User Can Now Login
        res_login_active = self.client.post(
            "/login",
            data={"username": "contact@greenbistro.test", "password": "SecurePassword123!"},
        )
        self.assertEqual(res_login_active.status_code, 200)
        user_jwt = res_login_active.json()["access_token"]

        # Step 8: User Accesses Protected Endpoint (/users/me)
        res_me = self.client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {user_jwt}"},
        )
        self.assertEqual(res_me.status_code, 200)
        me_data = res_me.json()
        self.assertEqual(me_data["email"], "contact@greenbistro.test")
        self.assertEqual(me_data["status"], "active")
        self.assertTrue(me_data["email_verified"])

    # --------------------------------------------------------------------------
    # 2. Rejection Flow
    # --------------------------------------------------------------------------
    def test_admin_rejection_flow(self):
        self._create_admin_user()
        admin_token = self._get_admin_token()

        # Signup and verify email
        signup_payload = {
            "full_name": "Suspicious NGO",
            "organization_name": "Fake Org",
            "email": "fake@ngo.test",
            "password": "Password123!",
            "role": "NGO",
        }
        self.client.post("/auth/signup", json=signup_payload)
        raw_token = self.sent_emails[0]["raw_token"]
        self.client.get(f"/auth/verify-email?token={raw_token}")

        with Session(self.test_engine) as session:
            user = session.exec(select(User).where(User.email == "fake@ngo.test")).first()
            user_id = user.id

        # Admin rejects user
        res_reject = self.client.patch(
            f"/admin/users/{user_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res_reject.status_code, 200)
        self.assertEqual(res_reject.json()["status"], "rejected")

        # Rejected user cannot login
        res_login = self.client.post(
            "/login",
            data={"username": "fake@ngo.test", "password": "Password123!"},
        )
        self.assertEqual(res_login.status_code, 403)
        self.assertIn("rejected", res_login.json()["detail"].lower())

    # --------------------------------------------------------------------------
    # 3. Token Edge Cases: Invalid, Reused, Missing
    # --------------------------------------------------------------------------
    def test_invalid_verification_token(self):
        res = self.client.get("/auth/verify-email?token=completely_invalid_random_token")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid or already-used", res.json()["detail"])

    def test_reused_verification_token(self):
        # Signup
        self.client.post("/auth/signup", json={
            "full_name": "Test User",
            "email": "reused@token.test",
            "password": "Password123!",
            "role": "RESTAURANT",
        })
        raw_token = self.sent_emails[0]["raw_token"]

        # First use -> Should succeed
        res1 = self.client.get(f"/auth/verify-email?token={raw_token}")
        self.assertEqual(res1.status_code, 200)

        # Second use -> Must fail (single-use token invalidated)
        res2 = self.client.get(f"/auth/verify-email?token={raw_token}")
        self.assertEqual(res2.status_code, 400)
        self.assertIn("Invalid or already-used", res2.json()["detail"])

    def test_missing_verification_token(self):
        res = self.client.get("/auth/verify-email")
        self.assertEqual(res.status_code, 422)  # Missing query param

    # --------------------------------------------------------------------------
    # 4. Resend Verification & Rate Limiting
    # --------------------------------------------------------------------------
    def test_resend_verification_and_cooldown(self):
        # Signup
        self.client.post("/auth/signup", json={
            "full_name": "Resend Tester",
            "email": "resend@test.com",
            "password": "Password123!",
            "role": "RESTAURANT",
        })
        first_raw_token = self.sent_emails[0]["raw_token"]

        # Immediate resend attempt -> Cooldown triggers 429
        res_cooldown = self.client.post(
            "/auth/resend-verification",
            json={"email": "resend@test.com"},
        )
        self.assertEqual(res_cooldown.status_code, 429)
        self.assertIn("wait", res_cooldown.json()["detail"].lower())

        # Simulate cooldown time elapsed by backdating last_verification_sent_at
        with Session(self.test_engine) as session:
            user = session.exec(select(User).where(User.email == "resend@test.com")).first()
            user.last_verification_sent_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
            session.add(user)
            session.commit()

        # Resend after cooldown -> Succeeds
        res_resend = self.client.post(
            "/auth/resend-verification",
            json={"email": "resend@test.com"},
        )
        self.assertEqual(res_resend.status_code, 200)
        self.assertEqual(len(self.sent_emails), 2)
        second_raw_token = self.sent_emails[1]["raw_token"]
        self.assertNotEqual(first_raw_token, second_raw_token)

        # Old token is invalidated, only new token works
        res_old = self.client.get(f"/auth/verify-email?token={first_raw_token}")
        self.assertEqual(res_old.status_code, 400)

        res_new = self.client.get(f"/auth/verify-email?token={second_raw_token}")
        self.assertEqual(res_new.status_code, 200)

    def test_resend_verification_nonexistent_user(self):
        res = self.client.post(
            "/auth/resend-verification",
            json={"email": "nonexistent@test.com"},
        )
        self.assertEqual(res.status_code, 404)

    def test_resend_verification_already_verified(self):
        # Create active user
        with Session(self.test_engine) as session:
            user = User(
                full_name="Active User",
                email="active@test.com",
                password_hash=hashing.get_hash_password("Password123!"),
                role=UserRole.NGO,
                status=UserStatus.ACTIVE,
                email_verified=True,
                approval_status=ApprovalStatus.APPROVED,
            )
            session.add(user)
            session.commit()

        res = self.client.post(
            "/auth/resend-verification",
            json={"email": "active@test.com"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("already verified", res.json()["detail"].lower())

    # --------------------------------------------------------------------------
    # 5. Access Control & Authorization Edge Cases
    # --------------------------------------------------------------------------
    def test_unauthorized_admin_approval(self):
        # Anonymous attempt
        res = self.client.patch("/admin/users/1/approve")
        self.assertEqual(res.status_code, 401)

    def test_normal_user_cannot_approve(self):
        # Create an active normal user
        with Session(self.test_engine) as session:
            normal_user = User(
                full_name="Normal NGO",
                email="normal@ngo.test",
                password_hash=hashing.get_hash_password("Password123!"),
                role=UserRole.NGO,
                status=UserStatus.ACTIVE,
                email_verified=True,
                approval_status=ApprovalStatus.APPROVED,
            )
            session.add(normal_user)
            session.commit()

        res_login = self.client.post(
            "/login",
            data={"username": "normal@ngo.test", "password": "Password123!"},
        )
        normal_token = res_login.json()["access_token"]

        # Normal user attempts admin approve
        res_approve = self.client.patch(
            "/admin/users/1/approve",
            headers={"Authorization": f"Bearer {normal_token}"},
        )
        self.assertEqual(res_approve.status_code, 403)
        self.assertIn("Admin access required", res_approve.json()["detail"])

    def test_admin_cannot_approve_pending_email_user(self):
        self._create_admin_user()
        admin_token = self._get_admin_token()

        # Signup user (remains in pending_email)
        self.client.post("/auth/signup", json={
            "full_name": "Unverified User",
            "email": "unverified@test.com",
            "password": "Password123!",
            "role": "RESTAURANT",
        })
        with Session(self.test_engine) as session:
            u = session.exec(select(User).where(User.email == "unverified@test.com")).first()
            user_id = u.id

        # Admin tries to approve before email verification
        res = self.client.patch(
            f"/admin/users/{user_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("before email verification", res.json()["detail"].lower())

    def test_admin_approving_already_active_user(self):
        self._create_admin_user()
        admin_token = self._get_admin_token()

        with Session(self.test_engine) as session:
            user = User(
                full_name="Already Active",
                email="already@active.test",
                password_hash=hashing.get_hash_password("Password123!"),
                role=UserRole.NGO,
                status=UserStatus.ACTIVE,
                email_verified=True,
                approval_status=ApprovalStatus.APPROVED,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id

        res = self.client.patch(
            f"/admin/users/{user_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("already active", res.json()["detail"].lower())

    def test_admin_rejecting_already_rejected_user(self):
        self._create_admin_user()
        admin_token = self._get_admin_token()

        with Session(self.test_engine) as session:
            user = User(
                full_name="Already Rejected",
                email="already@rejected.test",
                password_hash=hashing.get_hash_password("Password123!"),
                role=UserRole.NGO,
                status=UserStatus.REJECTED,
                email_verified=True,
                approval_status=ApprovalStatus.REJECTED,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id

        res = self.client.patch(
            f"/admin/users/{user_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("already rejected", res.json()["detail"].lower())

    def test_duplicate_email_signup_rejected(self):
        payload = {
            "full_name": "First User",
            "email": "duplicate@test.com",
            "password": "Password123!",
            "role": "RESTAURANT",
        }
        res1 = self.client.post("/auth/signup", json=payload)
        self.assertEqual(res1.status_code, 201)

        res2 = self.client.post("/auth/signup", json=payload)
        self.assertEqual(res2.status_code, 400)
        self.assertIn("already registered", res2.json()["detail"].lower())

    def test_admin_signup_forbidden(self):
        payload = {
            "full_name": "Wannabe Admin",
            "email": "hacker@test.com",
            "password": "Password123!",
            "role": "ADMIN",
        }
        res = self.client.post("/auth/signup", json=payload)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Admin accounts cannot be created", res.json()["detail"])


    def test_pending_email_user_accessing_protected_api(self):
        # Create user in pending_email state
        with Session(self.test_engine) as session:
            user = User(
                full_name="Pending Email User",
                email="pending_email@test.com",
                password_hash=hashing.get_hash_password("Password123!"),
                role=UserRole.RESTAURANT,
                status=UserStatus.PENDING_EMAIL,
                email_verified=False,
            )
            session.add(user)
            session.commit()

        # Generate JWT token directly
        jwt_token = token.create_access_token({"sub": "pending_email@test.com"})

        # Protected API access must be 403 Forbidden
        res = self.client.get("/users/me", headers={"Authorization": f"Bearer {jwt_token}"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("not verified", res.json()["detail"].lower())

    def test_pending_admin_user_accessing_protected_api(self):
        # Create user in pending_admin state
        with Session(self.test_engine) as session:
            user = User(
                full_name="Pending Admin User",
                email="pending_admin@test.com",
                password_hash=hashing.get_hash_password("Password123!"),
                role=UserRole.RESTAURANT,
                status=UserStatus.PENDING_ADMIN,
                email_verified=True,
            )
            session.add(user)
            session.commit()

        jwt_token = token.create_access_token({"sub": "pending_admin@test.com"})

        # Protected API access must be 403 Forbidden
        res = self.client.get("/users/me", headers={"Authorization": f"Bearer {jwt_token}"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("pending admin approval", res.json()["detail"].lower())

    def test_rejected_user_accessing_protected_api(self):
        # Create user in rejected state
        with Session(self.test_engine) as session:
            user = User(
                full_name="Rejected User",
                email="rejected@test.com",
                password_hash=hashing.get_hash_password("Password123!"),
                role=UserRole.NGO,
                status=UserStatus.REJECTED,
                email_verified=True,
            )
            session.add(user)
            session.commit()

        jwt_token = token.create_access_token({"sub": "rejected@test.com"})

        # Protected API access must be 403 Forbidden
        res = self.client.get("/users/me", headers={"Authorization": f"Bearer {jwt_token}"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("rejected", res.json()["detail"].lower())

    def test_admin_approval_via_legacy_patch_endpoint(self):
        self._create_admin_user()
        admin_token = self._get_admin_token()

        with Session(self.test_engine) as session:
            user = User(
                full_name="Legacy Review User",
                email="legacy@test.com",
                password_hash=hashing.get_hash_password("Password123!"),
                role=UserRole.NGO,
                status=UserStatus.PENDING_ADMIN,
                email_verified=True,
                approval_status=ApprovalStatus.PENDING,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id

        # PATCH /admin/users/{user_id}/approval with {"approval_status": "APPROVED"}
        res = self.client.patch(
            f"/admin/users/{user_id}/approval",
            json={"approval_status": "APPROVED"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "active")
        self.assertEqual(res.json()["approval_status"], "APPROVED")

    def test_verify_email_empty_token(self):
        res = self.client.get("/auth/verify-email?token=   ")
        self.assertEqual(res.status_code, 400)
        self.assertIn("required", res.json()["detail"].lower())

    def test_live_vercel_url_generation(self):
        # Simulate request arriving at a live Vercel deployment host
        headers = {
            "x-forwarded-host": "foodshare-backend.vercel.app",
            "x-forwarded-proto": "https",
        }
        res = self.client.post(
            "/auth/signup",
            json={
                "full_name": "Vercel Test User",
                "email": "vercel@user.test",
                "password": "Password123!",
                "role": "RESTAURANT",
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(self.sent_emails), 1)

        raw_token = self.sent_emails[0]["raw_token"]
        request_base_url = self.sent_emails[0]["request_base_url"]
        self.assertEqual(request_base_url, "https://foodshare-backend.vercel.app")

        # Resolve URL using get_verification_url
        resolved_url = email_service.get_verification_url(
            raw_token=raw_token,
            request_base_url=request_base_url,
        )
        self.assertTrue(resolved_url.startswith("https://foodshare-backend.vercel.app/verify-email?token="))
        self.assertNotIn("localhost", resolved_url)

    def test_browser_html_verification_response(self):
        # Signup user
        self.client.post(
            "/auth/signup",
            json={
                "full_name": "Browser User",
                "email": "browser@user.test",
                "password": "Password123!",
                "role": "RESTAURANT",
            },
        )
        raw_token = self.sent_emails[0]["raw_token"]

        # Browser clicks link: sends Accept: text/html
        res_html = self.client.get(
            f"/verify-email?token={raw_token}",
            headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        self.assertEqual(res_html.status_code, 200)
        self.assertIn("text/html", res_html.headers["content-type"])
        self.assertIn("Email Verified!", res_html.text)
        self.assertIn("Administrator Review", res_html.text)

        # Second click in browser shows user-friendly error page
        res_reused = self.client.get(
            f"/verify-email?token={raw_token}",
            headers={"Accept": "text/html"},
        )
        self.assertEqual(res_reused.status_code, 400)
        self.assertIn("text/html", res_reused.headers["content-type"])
        self.assertIn("Link Expired or Already Used", res_reused.text)

    def test_token_expires_after_5_minutes(self):
        """Tokens older than 5 minutes must be rejected and invalidated."""
        signup_res = self.client.post(
            "/auth/signup",
            json={
                "full_name": "Expiring User",
                "email": "expiring@user.test",
                "password": "Password123!",
                "role": "RESTAURANT",
            },
        )
        self.assertEqual(signup_res.status_code, 201)
        raw_token = self.sent_emails[0]["raw_token"]

        # Simulate time moving past 5 minutes in database
        with Session(self.test_engine) as session:
            user = session.exec(select(User).where(User.email == "expiring@user.test")).first()
            self.assertIsNotNone(user.verification_token_expires_at)
            # Set expiration to 10 minutes in the past
            user.verification_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
            session.add(user)
            session.commit()

        # Attempt verification via API
        verify_res = self.client.get(f"/auth/verify-email?token={raw_token}")
        self.assertEqual(verify_res.status_code, 400)
        self.assertIn("expired", verify_res.json()["detail"].lower())

        # Verify token was invalidated in database
        with Session(self.test_engine) as session:
            user = session.exec(select(User).where(User.email == "expiring@user.test")).first()
            self.assertIsNone(user.verification_token_hash)
            self.assertEqual(user.status, UserStatus.PENDING_EMAIL)

        # Attempt verification via browser (Accept: text/html)
        browser_res = self.client.get(
            f"/verify-email?token={raw_token}",
            headers={"Accept": "text/html"},
        )
        self.assertEqual(browser_res.status_code, 400)
        self.assertIn("text/html", browser_res.headers["content-type"])
        self.assertIn("Link Expired or Already Used", browser_res.text)


if __name__ == "__main__":
    unittest.main()

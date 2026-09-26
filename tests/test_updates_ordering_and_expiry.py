import unittest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
import jwt

from config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
import database as d_b
from main import app
from models import (
    ApprovalStatus,
    Donation,
    DonationStatus,
    PickupRequest,
    PickupRequestStatus,
    User,
    UserRole,
    UserStatus,
)
from security.hashing import get_hash_password
from security.token import create_access_token
from ai.generation.prompt import SYSTEM_PROMPT, PROMPT_VERSION


class TestUpdatesOrderingAndExpiry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(cls.engine)

        def get_test_session():
            with Session(cls.engine) as session:
                yield session

        app.dependency_overrides[d_b.get_session] = get_test_session
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def setUp(self):
        SQLModel.metadata.drop_all(self.engine)
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine) as session:
            # Create Restaurant
            self.restaurant = User(
                email="restaurant@test.com",
                full_name="Tasty Bites",
                organization_name="Tasty Bites Cafe",
                password_hash=get_hash_password("Secret123!"),
                role=UserRole.RESTAURANT,
                status=UserStatus.ACTIVE,
                email_verified=True,
                approval_status=ApprovalStatus.APPROVED,
            )
            # Create NGO
            self.ngo = User(
                email="ngo@test.com",
                full_name="Care NGO",
                organization_name="Care NGO Team",
                password_hash=get_hash_password("Secret123!"),
                role=UserRole.NGO,
                status=UserStatus.ACTIVE,
                email_verified=True,
                approval_status=ApprovalStatus.APPROVED,
            )
            # Create Admin
            self.admin = User(
                email="admin@test.com",
                full_name="Admin Boss",
                password_hash=get_hash_password("Secret123!"),
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                email_verified=True,
                approval_status=ApprovalStatus.APPROVED,
            )
            session.add_all([self.restaurant, self.ngo, self.admin])
            session.commit()
            session.refresh(self.restaurant)
            session.refresh(self.ngo)
            session.refresh(self.admin)

            self.restaurant_token = create_access_token({"sub": self.restaurant.email})
            self.ngo_token = create_access_token({"sub": self.ngo.email})
            self.admin_token = create_access_token({"sub": self.admin.email})

    def test_persistent_session_token_expiry(self):
        # 1. ACCESS_TOKEN_EXPIRE_MINUTES is 525600
        self.assertEqual(ACCESS_TOKEN_EXPIRE_MINUTES, 525600)

        # 2. Token expiration is roughly 1 year in the future
        payload = jwt.decode(self.restaurant_token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        self.assertIsNotNone(exp)
        exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
        now_dt = datetime.now(timezone.utc)
        diff_days = (exp_dt - now_dt).total_seconds() / 86400
        self.assertTrue(364 <= diff_days <= 366, f"Expected ~365 days, got {diff_days}")

    def test_donation_feed_ordering_and_expired_filtering(self):
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            # Older active donation
            d1 = Donation(
                restaurant_id=self.restaurant.id,
                food_name="Old Active Bread",
                quantity=5.0,
                unit="kg",
                prepared_at=now - timedelta(hours=3),
                pickup_deadline=now + timedelta(hours=5),
                pickup_area="Gulshan",
                pickup_address="Road 1, House 2",
                status=DonationStatus.AVAILABLE,
                created_at=now - timedelta(hours=3),
            )
            # Newer active donation
            d2 = Donation(
                restaurant_id=self.restaurant.id,
                food_name="Newer Active Curry",
                quantity=10.0,
                unit="boxes",
                prepared_at=now - timedelta(hours=1),
                pickup_deadline=now + timedelta(hours=4),
                pickup_area="Gulshan",
                pickup_address="Road 1, House 2",
                status=DonationStatus.AVAILABLE,
                created_at=now - timedelta(hours=1),
            )
            # Expired donation (pickup deadline is in the past)
            d3 = Donation(
                restaurant_id=self.restaurant.id,
                food_name="Expired Soup",
                quantity=3.0,
                unit="liters",
                prepared_at=now - timedelta(hours=10),
                pickup_deadline=now - timedelta(hours=1),
                pickup_area="Gulshan",
                pickup_address="Road 1, House 2",
                status=DonationStatus.AVAILABLE,
                created_at=now - timedelta(hours=10),
            )
            session.add_all([d1, d2, d3])
            session.commit()
            session.refresh(d1)
            session.refresh(d2)
            session.refresh(d3)

        headers = {"Authorization": f"Bearer {self.ngo_token}"}

        # Test Public Feed GET /donations
        res = self.client.get("/donations", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        items = data["items"]

        # Expired donation must NOT appear in public feed
        item_names = [item["food_name"] for item in items]
        self.assertIn("Newer Active Curry", item_names)
        self.assertIn("Old Active Bread", item_names)
        self.assertNotIn("Expired Soup", item_names)

        # Ordering must be newest first (d2 then d1)
        self.assertEqual(items[0]["food_name"], "Newer Active Curry")
        self.assertEqual(items[1]["food_name"], "Old Active Bread")

        # Verify GET /donations/available alias also returns the same
        res_avail = self.client.get("/donations/available", headers=headers)
        self.assertEqual(res_avail.status_code, 200)
        avail_items = res_avail.json()["items"]
        self.assertEqual([i["food_name"] for i in avail_items], ["Newer Active Curry", "Old Active Bread"])

        # Check DB to verify d3 was auto-transitioned to EXPIRED
        with Session(self.engine) as session:
            db_d3 = session.get(Donation, d3.id)
            self.assertEqual(db_d3.status, DonationStatus.EXPIRED)

        # Test Restaurant Donations GET /donations/my
        # Retains expired donation so restaurant can view past history!
        r_headers = {"Authorization": f"Bearer {self.restaurant_token}"}
        res_my = self.client.get("/donations/my", headers=r_headers)
        self.assertEqual(res_my.status_code, 200)
        my_items = res_my.json()["items"]
        my_names = [i["food_name"] for i in my_items]

        self.assertIn("Expired Soup", my_names)
        self.assertEqual(len(my_items), 3)
        # Restaurant queries must also be ordered newest first (created_at DESC)
        self.assertEqual(my_items[0]["food_name"], "Newer Active Curry")
        self.assertEqual(my_items[1]["food_name"], "Old Active Bread")
        self.assertEqual(my_items[2]["food_name"], "Expired Soup")

        # Test alias GET /donations/restaurant
        res_rest = self.client.get("/donations/restaurant", headers=r_headers)
        self.assertEqual(res_rest.status_code, 200)
        self.assertEqual([i["food_name"] for i in res_rest.json()["items"]], my_names)

    def test_pickup_requests_ordering(self):
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            d = Donation(
                restaurant_id=self.restaurant.id,
                food_name="Sandwiches",
                quantity=10.0,
                unit="packs",
                prepared_at=now - timedelta(hours=1),
                pickup_deadline=now + timedelta(hours=5),
                pickup_area="Banani",
                pickup_address="Block B",
                status=DonationStatus.AVAILABLE,
            )
            session.add(d)
            session.commit()
            session.refresh(d)

            # Create second NGO for testing multiple requests
            ngo2 = User(
                email="ngo2@test.com",
                full_name="Second Hope NGO",
                password_hash=get_hash_password("Secret123!"),
                role=UserRole.NGO,
                status=UserStatus.ACTIVE,
                email_verified=True,
                approval_status=ApprovalStatus.APPROVED,
            )
            session.add(ngo2)
            session.commit()
            session.refresh(ngo2)

            # Request 1 (earlier)
            req1 = PickupRequest(
                donation_id=d.id,
                ngo_id=self.ngo.id,
                estimated_pickup_at=now + timedelta(hours=2),
                message="First request",
                requested_at=now - timedelta(minutes=30),
            )
            # Request 2 (later / newer)
            req2 = PickupRequest(
                donation_id=d.id,
                ngo_id=ngo2.id,
                estimated_pickup_at=now + timedelta(hours=3),
                message="Second request",
                requested_at=now - timedelta(minutes=5),
            )
            session.add_all([req1, req2])
            session.commit()
            donation_id = d.id
            ngo2_email = ngo2.email

        # Check restaurant's view of donation pickup requests: GET /donations/{id}/pickup-requests
        r_headers = {"Authorization": f"Bearer {self.restaurant_token}"}
        res = self.client.get(f"/donations/{donation_id}/pickup-requests", headers=r_headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()["items"]
        self.assertEqual(len(items), 2)
        # Newest first
        self.assertEqual(items[0]["message"], "Second request")
        self.assertEqual(items[1]["message"], "First request")

        # Test alias /donations/{id}/requests
        res_alias = self.client.get(f"/donations/{donation_id}/requests", headers=r_headers)
        self.assertEqual(res_alias.status_code, 200)
        self.assertEqual(res_alias.json()["items"][0]["message"], "Second request")

        # Check NGO's view of my pickup requests: GET /pickup-requests/my
        ngo2_token = create_access_token({"sub": ngo2_email})
        res_ngo = self.client.get("/pickups/my", headers={"Authorization": f"Bearer {ngo2_token}"})
        self.assertEqual(res_ngo.status_code, 200)
        self.assertEqual(len(res_ngo.json()["items"]), 1)
        self.assertEqual(res_ngo.json()["items"][0]["message"], "Second request")

    def test_admin_users_ordering(self):
        # Admin listing users: GET /admin/users and GET /admin/users/pending
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.get("/admin/users", headers=headers)
        self.assertEqual(res.status_code, 200)
        users = res.json()["items"]
        # Users must be ordered newest first (created_at DESC)
        created_times = [u["created_at"] for u in users]
        self.assertEqual(created_times, sorted(created_times, reverse=True))

    def test_ai_chatbot_system_prompt(self):
        # Verify FoodShare Guide persona and strict constraints
        self.assertIn("FoodShare Guide", SYSTEM_PROMPT)
        self.assertIn("NO POST OR FOOD DESCRIPTIONS", SYSTEM_PROMPT)
        self.assertIn("NO MARKETING OR PROMOTIONAL COPY", SYSTEM_PROMPT)
        self.assertIn("NO RECIPES OR COOKING ADVICE", SYSTEM_PROMPT)
        self.assertIn("NO CREATIVE WRITING", SYSTEM_PROMPT)
        self.assertIn("I am the FoodShare Guide. I cannot generate food descriptions", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()

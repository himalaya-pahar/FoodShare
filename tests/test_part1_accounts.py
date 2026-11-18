import unittest
from datetime import timedelta
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import database as d_b
from config import ALGORITHM, SECRET_KEY
from main import app
from models import (
    ApprovalStatus,
    MediaUploadStatus,
    User,
    UserProfileImage,
    UserRole,
    UserStatus,
)
from security.hashing import get_hash_password, verify_password
from security.token import create_access_token


class TestPart1Accounts(unittest.TestCase):
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
        app.dependency_overrides.pop(d_b.get_session, None)

    def setUp(self):
        SQLModel.metadata.drop_all(self.engine)
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine) as session:
            self.restaurant = self._add_user(
                session, "restaurant@part1.test", UserRole.RESTAURANT
            )
            self.other_restaurant = self._add_user(
                session, "other-restaurant@part1.test", UserRole.RESTAURANT
            )
            self.ngo = self._add_user(
                session, "ngo@part1.test", UserRole.NGO
            )
            self.admin = self._add_user(
                session, "admin@part1.test", UserRole.ADMIN
            )
            session.commit()
            for user in (
                self.restaurant,
                self.other_restaurant,
                self.ngo,
                self.admin,
            ):
                session.refresh(user)

        self.restaurant_token = create_access_token(
            {"sub": self.restaurant.email}
        )
        self.other_restaurant_token = create_access_token(
            {"sub": self.other_restaurant.email}
        )
        self.ngo_token = create_access_token({"sub": self.ngo.email})
        self.admin_token = create_access_token({"sub": self.admin.email})

    @staticmethod
    def _add_user(session, email, role):
        user = User(
            full_name=email.split("@")[0],
            email=email,
            password_hash=get_hash_password("CorrectPassword123!"),
            role=role,
            status=UserStatus.ACTIVE,
            email_verified=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        session.add(user)
        session.flush()
        return user

    def _headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_signup_hashes_password_and_does_not_expose_it(self):
        payload = {
            "full_name": "  New Restaurant  ",
            "email": " New@Part1.Test ",
            "password": "StrongPassword123!",
            "role": "RESTAURANT",
        }
        with patch(
            "repository.authenticate.email_service.send_verification_email",
            return_value=True,
        ):
            response = self.client.post("/signup", json=payload)

        self.assertEqual(response.status_code, 201)
        result = response.json()
        self.assertEqual(result["email"], "new@part1.test")
        self.assertEqual(result["full_name"], "New Restaurant")
        self.assertNotIn("password", result)
        self.assertNotIn("password_hash", result)

        with Session(self.engine) as session:
            saved_user = session.get(User, result["id"])
            self.assertNotEqual(saved_user.password_hash, payload["password"])
            self.assertTrue(
                verify_password(payload["password"], saved_user.password_hash)
            )

    def test_login_accepts_valid_credentials_and_rejects_invalid_credentials(self):
        valid = self.client.post(
            "/login",
            data={
                "username": self.restaurant.email.upper(),
                "password": "CorrectPassword123!",
            },
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["token_type"], "bearer")
        token_payload = jwt.decode(
            valid.json()["access_token"],
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        self.assertEqual(token_payload["sub"], self.restaurant.email)
        self.assertIn("exp", token_payload)
        self.assertEqual(
            self.client.get(
                "/users/me",
                headers=self._headers(valid.json()["access_token"]),
            ).status_code,
            200,
        )

        for username, password in (
            (self.restaurant.email, "WrongPassword123!"),
            ("missing@part1.test", "CorrectPassword123!"),
        ):
            with self.subTest(username=username):
                invalid = self.client.post(
                    "/login",
                    data={"username": username, "password": password},
                )
                self.assertEqual(invalid.status_code, 401)

    def test_protected_route_rejects_invalid_expired_and_subjectless_tokens(self):
        future_expiry = create_access_token(
            {"sub": self.restaurant.email},
            expires=timedelta(seconds=-1),
        )
        subjectless = jwt.encode(
            {"exp": 4_102_444_800},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        for invalid_token in ("not-a-jwt", future_expiry, subjectless):
            with self.subTest(token=invalid_token[:12]):
                response = self.client.get(
                    "/users/me",
                    headers=self._headers(invalid_token),
                )
                self.assertEqual(response.status_code, 401)

        self.assertEqual(self.client.get("/users/me").status_code, 401)

    def test_role_permissions_reject_wrong_roles_and_non_admins(self):
        donation_response = self.client.post(
            "/donations/",
            json={},
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(donation_response.status_code, 403)

        admin_response = self.client.get(
            "/admin/stats",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(admin_response.status_code, 403)

        self.assertEqual(
            self.client.get("/admin/stats").status_code,
            401,
        )

    def test_admin_lists_users_stats_and_deletes_only_non_admin_accounts(self):
        admin_headers = self._headers(self.admin_token)
        stats = self.client.get("/admin/stats", headers=admin_headers)
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()["total_users"], 4)
        self.assertEqual(stats.json()["restaurant_users"], 2)
        self.assertEqual(stats.json()["ngo_users"], 1)

        users = self.client.get("/admin/users", headers=admin_headers)
        self.assertEqual(users.status_code, 200)
        self.assertEqual(users.json()["total"], 4)

        non_admin_delete = self.client.delete(
            f"/admin/users/{self.other_restaurant.id}",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(non_admin_delete.status_code, 403)

        deleted = self.client.delete(
            f"/admin/users/{self.other_restaurant.id}",
            headers=admin_headers,
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["message"], "User deleted successfully")

        admin_delete = self.client.delete(
            f"/admin/users/{self.admin.id}",
            headers=admin_headers,
        )
        self.assertEqual(admin_delete.status_code, 403)

    def test_profile_update_persists_cleaned_fields_and_rejects_blank_name(self):
        response = self.client.patch(
            "/users/me",
            json={
                "full_name": "  Updated Name  ",
                "area": "  North  ",
                "address": "  New address  ",
            },
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["full_name"], "Updated Name")
        self.assertEqual(response.json()["area"], "North")
        self.assertEqual(response.json()["address"], "New address")

        blank_name = self.client.patch(
            "/users/me",
            json={"full_name": "  "},
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(blank_name.status_code, 400)

        with Session(self.engine) as session:
            persisted = session.get(User, self.restaurant.id)
            self.assertEqual(persisted.full_name, "Updated Name")
            self.assertEqual(persisted.area, "North")

    def test_profile_image_upload_completion_and_delete_use_storage_mocks(self):
        with (
            patch(
                "repository.profile_image.create_profile_image_upload_target",
                return_value={
                    "storage_key": "profiles/test/image.jpg",
                    "upload_url": "https://storage.invalid/upload",
                },
            ) as upload_target,
            patch(
                "repository.profile_image.create_private_read_url",
                return_value="https://storage.invalid/image",
            ) as read_url,
            patch("repository.profile_image.supabase") as storage_client,
        ):
            upload_response = self.client.post(
                "/profile-image/upload-url",
                json={"content_type": "image/jpeg"},
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(upload_response.status_code, 201)
            self.assertEqual(
                upload_response.json()["upload_url"],
                "https://storage.invalid/upload",
            )
            image_id = upload_response.json()["image_id"]

            duplicate_upload = self.client.post(
                "/profile-image/upload-url",
                json={"content_type": "image/png"},
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(duplicate_upload.status_code, 409)

            complete = self.client.post(
                f"/profile-image/{image_id}/complete",
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(complete.status_code, 200)
            self.assertEqual(
                complete.json()["media_url"],
                "https://storage.invalid/image",
            )
            read_url.assert_called()

            current_image = self.client.get(
                "/profile-image/me",
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(current_image.status_code, 200)
            self.assertEqual(current_image.json()["id"], image_id)

            deleted = self.client.delete(
                f"/profile-image/{image_id}",
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(deleted.status_code, 204)
            storage_client.storage.from_.return_value.remove.assert_called_once()
            upload_target.assert_called_once()

        empty_image = self.client.get(
            "/profile-image/me",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(empty_image.status_code, 200)
        self.assertIsNone(empty_image.json())

    def test_profile_image_upload_validates_type_auth_and_ownership(self):
        invalid_type = self.client.post(
            "/profile-image/upload-url",
            json={"content_type": "image/gif"},
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(invalid_type.status_code, 422)

        unauthenticated = self.client.get("/profile-image/me")
        self.assertEqual(unauthenticated.status_code, 401)

        with Session(self.engine) as session:
            image = UserProfileImage(
                user_id=self.restaurant.id,
                content_type="image/jpeg",
                storage_key="profiles/restaurant/private.jpg",
                upload_status=MediaUploadStatus.PENDING,
            )
            session.add(image)
            session.commit()
            session.refresh(image)
            image_id = image.id

        not_owner = self.client.delete(
            f"/profile-image/{image_id}",
            headers=self._headers(self.other_restaurant_token),
        )
        self.assertEqual(not_owner.status_code, 403)


if __name__ == "__main__":
    unittest.main()

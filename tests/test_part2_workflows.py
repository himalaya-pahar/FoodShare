import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import database as d_b
from main import app
from models import (
    ApprovalStatus,
    AuditEntityType,
    Donation,
    DonationMedia,
    DonationStatus,
    MediaUploadStatus,
    PickupRequest,
    PickupRequestStatus,
    StatusHistory,
    User,
    UserRole,
    UserStatus,
)
from security.hashing import get_hash_password
from security.token import create_access_token


class TestPart2Workflows(unittest.TestCase):
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
        cls.client = TestClient(app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(d_b.get_session, None)

    def setUp(self):
        SQLModel.metadata.drop_all(self.engine)
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            self.restaurant = self._add_user(
                session, "restaurant@part2.test", UserRole.RESTAURANT
            )
            self.other_restaurant = self._add_user(
                session, "other-restaurant@part2.test", UserRole.RESTAURANT
            )
            self.ngo = self._add_user(session, "ngo@part2.test", UserRole.NGO)
            self.other_ngo = self._add_user(
                session, "other-ngo@part2.test", UserRole.NGO
            )
            self.admin = self._add_user(session, "admin@part2.test", UserRole.ADMIN)
            session.commit()
            for user in (
                self.restaurant,
                self.other_restaurant,
                self.ngo,
                self.other_ngo,
                self.admin,
            ):
                session.refresh(user)

        self.restaurant_token = self._token(self.restaurant)
        self.other_restaurant_token = self._token(self.other_restaurant)
        self.ngo_token = self._token(self.ngo)
        self.other_ngo_token = self._token(self.other_ngo)
        self.admin_token = self._token(self.admin)

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

    @staticmethod
    def _token(user):
        return create_access_token({"sub": user.email})

    @staticmethod
    def _headers(token):
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _donation_payload(**overrides):
        now = datetime.now(timezone.utc)
        payload = {
            "food_name": "Fresh sandwiches",
            "description": "Prepared today",
            "quantity": 12,
            "unit": "packs",
            "prepared_at": (now - timedelta(hours=1)).isoformat(),
            "pickup_deadline": (now + timedelta(hours=5)).isoformat(),
            "pickup_area": "Gulshan",
            "pickup_address": "Road 1, Building 2",
        }
        payload.update(overrides)
        return payload

    def _create_donation(self, **overrides):
        response = self.client.post(
            "/donations/",
            json=self._donation_payload(**overrides),
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _request_pickup(self, donation_id, ngo_token=None, **overrides):
        estimated_pickup_at = datetime.now(timezone.utc) + timedelta(hours=2)
        payload = {
            "estimated_pickup_at": estimated_pickup_at.isoformat(),
            "message": "We can collect this donation.",
        }
        payload.update(overrides)
        return self.client.post(
            f"/donations/{donation_id}/pickup-requests",
            json=payload,
            headers=self._headers(ngo_token or self.ngo_token),
        )

    def test_donation_creation_validates_fields_schedule_and_role(self):
        created = self._create_donation()
        self.assertEqual(created["status"], DonationStatus.AVAILABLE.value)
        self.assertEqual(created["restaurant_id"], self.restaurant.id)

        with Session(self.engine) as session:
            history = session.exec(
                select(StatusHistory).where(
                    StatusHistory.donation_id == created["id"]
                )
            ).all()
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0].action, "DONATION_CREATED")

        missing_field_payload = self._donation_payload()
        del missing_field_payload["pickup_address"]
        missing = self.client.post(
            "/donations/",
            json=missing_field_payload,
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(missing.status_code, 422)

        invalid_quantity = self.client.post(
            "/donations/",
            json=self._donation_payload(quantity=0),
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(invalid_quantity.status_code, 422)

        now = datetime.now(timezone.utc)
        invalid_schedule = self.client.post(
            "/donations/",
            json=self._donation_payload(
                prepared_at=now.isoformat(),
                pickup_deadline=(now - timedelta(seconds=1)).isoformat(),
            ),
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(invalid_schedule.status_code, 400)

        wrong_role = self.client.post(
            "/donations/",
            json=self._donation_payload(),
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(wrong_role.status_code, 403)
        self.assertEqual(
            self.client.post(
                "/donations/",
                json=self._donation_payload(),
            ).status_code,
            401,
        )

    def test_donation_update_cancel_and_history_enforce_ownership(self):
        donation = self._create_donation()
        donation_id = donation["id"]

        update = self.client.patch(
            f"/donations/{donation_id}",
            json={"food_name": "Updated meal", "quantity": 8},
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["food_name"], "Updated meal")
        self.assertEqual(update.json()["quantity"], 8)

        not_owner = self.client.patch(
            f"/donations/{donation_id}",
            json={"food_name": "Not yours"},
            headers=self._headers(self.other_restaurant_token),
        )
        self.assertEqual(not_owner.status_code, 403)

        now = datetime.now(timezone.utc)
        invalid_update = self.client.patch(
            f"/donations/{donation_id}",
            json={"pickup_deadline": (now - timedelta(days=1)).isoformat()},
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(invalid_update.status_code, 400)

        cancelled = self.client.post(
            f"/donations/{donation_id}/cancel",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], DonationStatus.CANCELLED.value)

        repeated_cancel = self.client.post(
            f"/donations/{donation_id}/cancel",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(repeated_cancel.status_code, 400)

        history = self.client.get(
            f"/donations/{donation_id}/history",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(history.status_code, 200)
        actions = [item["action"] for item in history.json()["items"]]
        self.assertIn("DONATION_CREATED", actions)
        self.assertIn("DONATION_CANCELLED", actions)

        forbidden_history = self.client.get(
            f"/donations/{donation_id}/history",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(forbidden_history.status_code, 403)

    def test_donation_detail_area_filter_and_query_boundaries(self):
        donation = self._create_donation()
        another_area = self._create_donation(
            food_name="Fresh fruit",
            pickup_area="Dhanmondi",
        )

        detail = self.client.get(
            f"/donations/{donation['id']}",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], donation["id"])
        self.assertEqual(
            detail.json()["restaurant_full_name"],
            self.restaurant.full_name,
        )

        filtered = self.client.get(
            "/donations",
            params={"area": "Dhanmondi", "limit": 1},
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(
            [item["id"] for item in filtered.json()["items"]],
            [another_area["id"]],
        )

        invalid_limit = self.client.get(
            "/donations",
            params={"limit": 0},
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(invalid_limit.status_code, 422)

    def test_pickup_request_rejects_invalid_time_duplicate_and_wrong_role(self):
        donation = self._create_donation()
        donation_id = donation["id"]
        invalid_early = self._request_pickup(
            donation_id,
            estimated_pickup_at=(
                datetime.now(timezone.utc) - timedelta(hours=2)
            ).isoformat(),
        )
        self.assertEqual(invalid_early.status_code, 400)

        invalid_late = self._request_pickup(
            donation_id,
            estimated_pickup_at=(
                datetime.now(timezone.utc) + timedelta(days=1)
            ).isoformat(),
        )
        self.assertEqual(invalid_late.status_code, 400)

        valid = self._request_pickup(donation_id)
        self.assertEqual(valid.status_code, 201)
        self.assertEqual(valid.json()["status"], PickupRequestStatus.PENDING.value)

        duplicate = self._request_pickup(donation_id)
        self.assertEqual(duplicate.status_code, 409)

        missing_field = self.client.post(
            f"/donations/{donation_id}/pickup-requests",
            json={},
            headers=self._headers(self.other_ngo_token),
        )
        self.assertEqual(missing_field.status_code, 422)

        wrong_role = self._request_pickup(
            donation_id,
            ngo_token=self.restaurant_token,
        )
        self.assertEqual(wrong_role.status_code, 403)

        unauthenticated = self.client.post(
            f"/donations/{donation_id}/pickup-requests",
            json={
                "estimated_pickup_at": (
                    datetime.now(timezone.utc) + timedelta(hours=1)
                ).isoformat()
            },
        )
        self.assertEqual(unauthenticated.status_code, 401)

    def test_acceptance_rejects_other_requests_and_completes_pickup_journey(self):
        donation = self._create_donation()
        request = self._request_pickup(donation["id"])
        other_request = self._request_pickup(
            donation["id"],
            ngo_token=self.other_ngo_token,
        )
        self.assertEqual(request.status_code, 201)
        self.assertEqual(other_request.status_code, 201)

        premature_completion = self.client.post(
            f"/donations/{donation['id']}/complete",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(premature_completion.status_code, 400)
        premature_collection = self.client.post(
            f"/pickup-requests/{request.json()['id']}/collect",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(premature_collection.status_code, 400)

        unauthorized_accept = self.client.post(
            f"/pickup-requests/{request.json()['id']}/accept",
            headers=self._headers(self.other_restaurant_token),
        )
        self.assertEqual(unauthorized_accept.status_code, 403)

        accepted = self.client.post(
            f"/pickup-requests/{request.json()['id']}/accept",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], PickupRequestStatus.ACCEPTED.value)

        with Session(self.engine) as session:
            saved_donation = session.get(Donation, donation["id"])
            declined = session.get(PickupRequest, other_request.json()["id"])
            self.assertEqual(saved_donation.status, DonationStatus.RESERVED)
            self.assertEqual(declined.status, PickupRequestStatus.REJECTED)

        repeated_accept = self.client.post(
            f"/pickup-requests/{request.json()['id']}/accept",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(repeated_accept.status_code, 400)

        wrong_ngo_collect = self.client.post(
            f"/pickup-requests/{request.json()['id']}/collect",
            headers=self._headers(self.other_ngo_token),
        )
        self.assertEqual(wrong_ngo_collect.status_code, 403)

        collected = self.client.post(
            f"/pickup-requests/{request.json()['id']}/collect",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(collected.status_code, 200)
        self.assertEqual(collected.json()["status"], PickupRequestStatus.COLLECTED.value)

        completed = self.client.post(
            f"/donations/{donation['id']}/complete",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], DonationStatus.COMPLETED.value)

        pickup_history = self.client.get(
            f"/pickup-requests/{request.json()['id']}/history",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(pickup_history.status_code, 200)
        self.assertIn(
            "PICKUP_REQUEST_ACCEPTED",
            [item["action"] for item in pickup_history.json()],
        )
        donation_history = self.client.get(
            f"/donations/{donation['id']}/history",
            headers=self._headers(self.restaurant_token),
        )
        self.assertIn(
            "DONATION_COMPLETED",
            [item["action"] for item in donation_history.json()["items"]],
        )

        journey = self.client.get(
            "/history/donations",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(journey.status_code, 200)
        self.assertEqual(journey.json()["items"][0]["current_status"], "COMPLETED")
        self.assertIn(
            "COMPLETED",
            journey.json()["items"][0]["status_timestamps"],
        )
        pickup_journey = self.client.get(
            "/history/pickups",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(pickup_journey.status_code, 200)
        self.assertEqual(
            pickup_journey.json()["items"][0]["current_status"],
            "COMPLETED",
        )
        my_requests = self.client.get(
            "/pickup-requests/my",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(my_requests.status_code, 200)
        self.assertEqual(my_requests.json()["items"][0]["id"], request.json()["id"])
        my_pickup_history = self.client.get(
            "/pickup-requests/my/history",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(my_pickup_history.status_code, 200)
        self.assertIn(
            "PICKUP_REQUEST_COLLECTED",
            [item["action"] for item in my_pickup_history.json()["items"]],
        )

    def test_reject_and_withdraw_transitions_are_recorded(self):
        donation = self._create_donation()
        pickup_request = self._request_pickup(donation["id"]).json()
        other_owner_withdrawal = self.client.post(
            f"/pickup-requests/{pickup_request['id']}/withdraw",
            headers=self._headers(self.other_ngo_token),
        )
        self.assertEqual(other_owner_withdrawal.status_code, 403)
        premature_collection = self.client.post(
            f"/pickup-requests/{pickup_request['id']}/collect",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(premature_collection.status_code, 400)

        rejected = self.client.post(
            f"/pickup-requests/{pickup_request['id']}/reject",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["status"], PickupRequestStatus.REJECTED.value)
        cannot_accept_rejected = self.client.post(
            f"/pickup-requests/{pickup_request['id']}/accept",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(cannot_accept_rejected.status_code, 400)

        second_donation = self._create_donation(food_name="Second meal")
        withdrawable = self._request_pickup(second_donation["id"]).json()
        withdrawn = self.client.post(
            f"/pickup-requests/{withdrawable['id']}/withdraw",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(withdrawn.status_code, 200)
        self.assertEqual(withdrawn.json()["status"], PickupRequestStatus.WITHDRAWN.value)

        with Session(self.engine) as session:
            history_actions = session.exec(
                select(StatusHistory.action).where(
                    StatusHistory.entity_type == AuditEntityType.PICKUP_REQUEST
                )
            ).all()
        self.assertIn("PICKUP_REQUEST_REJECTED", history_actions)
        self.assertIn("PICKUP_REQUEST_WITHDRAWN", history_actions)

    def test_donation_media_upload_completion_order_and_limits(self):
        donation = self._create_donation()
        donation_id = donation["id"]

        with (
            patch(
                "repository.donation_media.create_donation_media_upload_target",
                side_effect=lambda key: {
                    "storage_key": key,
                    "upload_url": f"https://storage.invalid/{key}",
                },
            ),
            patch(
                "repository.donation_media.create_private_read_url",
                side_effect=lambda bucket, key, expires_in=3600: (
                    f"https://storage.invalid/read/{key}"
                ),
            ),
            patch("repository.donation_media.supabase") as storage_client,
        ):
            image_upload = self.client.post(
                f"/donations/{donation_id}/media/upload-url",
                json={"content_type": "image/jpeg", "sort_order": 2},
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(image_upload.status_code, 201)
            video_upload = self.client.post(
                f"/donations/{donation_id}/media/upload-url",
                json={"content_type": "video/mp4", "sort_order": 0},
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(video_upload.status_code, 201)

            for upload in (image_upload, video_upload):
                complete = self.client.post(
                    f"/donation-media/{upload.json()['media_id']}/complete",
                    headers=self._headers(self.restaurant_token),
                )
                self.assertEqual(complete.status_code, 200)

            media = self.client.get(
                f"/donations/{donation_id}/media",
                headers=self._headers(self.ngo_token),
            )
            self.assertEqual(media.status_code, 200)
            self.assertEqual(
                [item["sort_order"] for item in media.json()],
                [0, 2],
            )

            delete_media = self.client.delete(
                f"/donation-media/{image_upload.json()['media_id']}",
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(delete_media.status_code, 204)
            storage_client.storage.from_.return_value.remove.assert_called_once()

        self.assertEqual(
            self.client.post(
                f"/donations/{donation_id}/media/upload-url",
                json={"content_type": "image/gif"},
                headers=self._headers(self.restaurant_token),
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                f"/donations/{donation_id}/media/upload-url",
                json={"content_type": "image/png"},
                headers=self._headers(self.ngo_token),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                f"/donations/{donation_id}/media/upload-url",
                json={"content_type": "image/png"},
                headers=self._headers(self.other_restaurant_token),
            ).status_code,
            403,
        )

        with Session(self.engine) as session:
            ready_media = session.exec(
                    select(DonationMedia).where(
                        DonationMedia.donation_id == donation_id,
                        DonationMedia.upload_status == MediaUploadStatus.READY,
                    )
                ).all()
            self.assertEqual(len(ready_media), 1)

    def test_donation_media_limits_and_pending_upload_completion_failure(self):
        donation = self._create_donation()
        donation_id = donation["id"]

        with patch(
            "repository.donation_media.create_donation_media_upload_target",
            side_effect=lambda key: {
                "storage_key": key,
                "upload_url": f"https://storage.invalid/{key}",
            },
        ):
            image_ids = []
            for sort_order in range(5):
                upload = self.client.post(
                    f"/donations/{donation_id}/media/upload-url",
                    json={
                        "content_type": "image/jpeg",
                        "sort_order": sort_order,
                    },
                    headers=self._headers(self.restaurant_token),
                )
                self.assertEqual(upload.status_code, 201)
                image_ids.append(upload.json()["media_id"])

            sixth_image = self.client.post(
                f"/donations/{donation_id}/media/upload-url",
                json={"content_type": "image/png"},
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(sixth_image.status_code, 400)

            video = self.client.post(
                f"/donations/{donation_id}/media/upload-url",
                json={"content_type": "video/mp4"},
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(video.status_code, 201)
            second_video = self.client.post(
                f"/donations/{donation_id}/media/upload-url",
                json={"content_type": "video/mp4"},
                headers=self._headers(self.restaurant_token),
            )
            self.assertEqual(second_video.status_code, 400)

        with patch(
            "repository.donation_media.create_private_read_url",
            side_effect=RuntimeError("test storage object not found"),
        ):
            not_uploaded = self.client.post(
                f"/donation-media/{image_ids[0]}/complete",
                headers=self._headers(self.restaurant_token),
            )
        self.assertEqual(not_uploaded.status_code, 400)

        visible_media = self.client.get(
            f"/donations/{donation_id}/media",
            headers=self._headers(self.ngo_token),
        )
        self.assertEqual(visible_media.status_code, 200)
        self.assertEqual(visible_media.json(), [])

        with Session(self.engine) as session:
            pending_upload = session.get(DonationMedia, image_ids[0])
            self.assertEqual(
                pending_upload.upload_status,
                MediaUploadStatus.PENDING,
            )

    def test_available_feed_and_activity_history_are_scoped_by_role(self):
        donation = self._create_donation()
        self.assertEqual(
            self.client.get(
                "/donations",
                headers=self._headers(self.ngo_token),
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/donations/my",
                headers=self._headers(self.ngo_token),
            ).status_code,
            403,
        )

        restaurant_history = self.client.get(
            "/donations/my/history",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(restaurant_history.status_code, 200)
        self.assertTrue(
            any(row["donation_id"] == donation["id"] for row in restaurant_history.json())
        )

        ngo_history = self.client.get(
            "/pickup-requests/my/history",
            headers=self._headers(self.restaurant_token),
        )
        self.assertEqual(ngo_history.status_code, 403)

        unauthenticated = self.client.get("/history/donations")
        self.assertEqual(unauthenticated.status_code, 401)


if __name__ == "__main__":
    unittest.main()

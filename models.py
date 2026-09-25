from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.types import String, TypeDecorator
from sqlmodel import Field, SQLModel


def utc_now():
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    RESTAURANT = "RESTAURANT"
    NGO = "NGO"
    ADMIN = "ADMIN"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class UserStatus(str, Enum):
    PENDING_EMAIL = "pending_email"
    PENDING_ADMIN = "pending_admin"
    ACTIVE = "active"
    REJECTED = "rejected"


class UserStatusType(TypeDecorator):
    """
    Robust TypeDecorator for UserStatus.
    Ensures that whether the database stores lowercase ('active') or uppercase
    enum names ('ACTIVE', 'PENDING_ADMIN'), it always maps seamlessly to UserStatus
    without throwing a SQLAlchemy LookupError.
    """
    impl = String(50)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, UserStatus):
            return value.value
        if isinstance(value, str):
            val_clean = value.lower().strip()
            for s in UserStatus:
                if s.value == val_clean or s.name.lower() == val_clean:
                    return s.value
            return val_clean
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, UserStatus):
            return value
        val_clean = str(value).lower().strip()
        for s in UserStatus:
            if s.value == val_clean or s.name.lower() == val_clean:
                return s
        return UserStatus(val_clean)


class DonationStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    COLLECTED = "COLLECTED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PickupRequestStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    COLLECTED = "COLLECTED"


class AuditEntityType(str, Enum):
    DONATION = "DONATION"
    PICKUP_REQUEST = "PICKUP_REQUEST"

class MediaType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"

class MediaUploadStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)

    full_name: str = Field(max_length=100)
    organization_name: Optional[str] = Field(default=None, max_length=150)

    email: str = Field(
        max_length=255,
        index=True,
        sa_column_kwargs={"unique": True},
    )
    password_hash: str = Field(max_length=255)

    role: UserRole = Field(index=True)
    status: UserStatus = Field(
        default=UserStatus.PENDING_EMAIL,
        sa_column=sa.Column(
            UserStatusType(),
            nullable=False,
            default=UserStatus.PENDING_EMAIL.value,
            index=True,
        ),
    )
    email_verified: bool = Field(default=False)
    email_verified_at: Optional[datetime] = Field(default=None)
    verification_token_hash: Optional[str] = Field(
        default=None,
        max_length=255,
        index=True,
    )
    last_verification_sent_at: Optional[datetime] = Field(default=None)
    verification_token_expires_at: Optional[datetime] = Field(default=None)

    approval_status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        index=True,
    )

    phone: Optional[str] = Field(default=None, max_length=30)
    address: Optional[str] = None
    area: Optional[str] = Field(default=None, max_length=100, index=True)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Donation(SQLModel, table=True):
    __tablename__ = "donations"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_donations_quantity_positive",
        ),
        CheckConstraint(
            "pickup_deadline > prepared_at",
            name="ck_donations_deadline_after_prepared",
        ),
        Index(
            "ix_donations_status_area_deadline",
            "status",
            "pickup_area",
            "pickup_deadline",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    restaurant_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    food_name: str = Field(max_length=150)
    description: Optional[str] = None

    quantity: float
    unit: str = Field(max_length=30)

    prepared_at: datetime
    pickup_deadline: datetime = Field(index=True)

    pickup_area: str = Field(max_length=100, index=True)
    pickup_address: str

    storage_notes: Optional[str] = None
    allergen_info: Optional[str] = None

    status: DonationStatus = Field(
        default=DonationStatus.AVAILABLE,
        index=True,
    )

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PickupRequest(SQLModel, table=True):
    __tablename__ = "pickup_requests"

    __table_args__ = (
        UniqueConstraint(
            "donation_id",
            "ngo_id",
            name="uq_pickup_request_donation_ngo",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    donation_id: int = Field(
        foreign_key="donations.id",
        index=True,
    )
    ngo_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    estimated_pickup_at: datetime
    message: Optional[str] = None

    status: PickupRequestStatus = Field(
        default=PickupRequestStatus.PENDING,
        index=True,
    )

    requested_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StatusHistory(SQLModel, table=True):
    __tablename__ = "status_history"

    id: Optional[int] = Field(default=None, primary_key=True)

    donation_id: int = Field(
        foreign_key="donations.id",
        index=True,
    )
    pickup_request_id: Optional[int] = Field(
        default=None,
        foreign_key="pickup_requests.id",
    )
    actor_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    entity_type: AuditEntityType
    action: str = Field(max_length=50)

    old_status: Optional[str] = Field(default=None, max_length=20)
    new_status: Optional[str] = Field(default=None, max_length=20)

    note: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class UserProfileImage(SQLModel, table=True):
    __tablename__ = "user_profile_images"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_profile_images_user"),
        UniqueConstraint(
            "storage_key",
            name="uq_user_profile_images_storage_key",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    content_type: str = Field(max_length=100)

    upload_status: MediaUploadStatus = Field(
        default=MediaUploadStatus.PENDING,
        index=True,
    )

    storage_key: str = Field(max_length=500)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DonationMedia(SQLModel, table=True):
    __tablename__ = "donation_media"

    __table_args__ = (
        CheckConstraint(
            "sort_order >= 0",
            name="ck_donation_media_sort_order",
        ),
        Index(
            "ix_donation_media_donation_sort_order",
            "donation_id",
            "sort_order",
        ),
        UniqueConstraint(
            "storage_key",
            name="uq_donation_media_storage_key",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    donation_id: int = Field(
        foreign_key="donations.id",
        index=True,
    )

    content_type: str = Field(max_length=100)

    upload_status: MediaUploadStatus = Field(
        default=MediaUploadStatus.PENDING,
        index=True,
    )

    media_type: MediaType = Field(index=True)

    storage_key: str = Field(max_length=500)

    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


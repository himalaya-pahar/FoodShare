from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
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
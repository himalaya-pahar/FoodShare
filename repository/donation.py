from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import select

import database as d_b
import schemas
from models import AuditEntityType, Donation, DonationStatus, User
from repository.status_history import add_status_history


def validate_schedule(
    prepared_at: datetime,
    pickup_deadline: datetime,
):
    if pickup_deadline <= prepared_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pickup deadline must be after prepared time",
        )


def create_donation(
    donation_data: schemas.DonationCreate,
    restaurant: User,
    db: d_b.SessionDep,
) -> Donation:
    validate_schedule(
        donation_data.prepared_at,
        donation_data.pickup_deadline,
    )

    new_donation = Donation(
        restaurant_id=restaurant.id,
        **donation_data.model_dump(),
    )

    db.add(new_donation)
    db.flush()

    add_status_history(
        db,
        donation_id=new_donation.id,
        actor_id=restaurant.id,
        entity_type=AuditEntityType.DONATION,
        action="DONATION_CREATED",
        new_status=DonationStatus.AVAILABLE.value,
    )

    db.commit()
    db.refresh(new_donation)

    return new_donation


def get_my_donations(
    restaurant: User,
    db: d_b.SessionDep,
) -> list[Donation]:
    return db.exec(
        select(Donation)
        .where(Donation.restaurant_id == restaurant.id)
        .order_by(Donation.created_at)
    ).all()


def get_available_donations(
    db: d_b.SessionDep,
    area: Optional[str] = None,
) -> list[Donation]:
    statement = select(Donation).where(
        Donation.status == DonationStatus.AVAILABLE
    )

    if area:
        statement = statement.where(
            Donation.pickup_area == area.strip()
        )

    return db.exec(
        statement.order_by(Donation.pickup_deadline)
    ).all()


def get_donation_by_id(
    donation_id: int,
    db: d_b.SessionDep,
) -> Donation:
    donation = db.get(Donation, donation_id)

    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation not found",
        )

    return donation


def update_donation(
    donation_id: int,
    donation_data: schemas.DonationUpdate,
    restaurant: User,
    db: d_b.SessionDep,
) -> Donation:
    donation = get_donation_by_id(donation_id, db)

    if donation.restaurant_id != restaurant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this donation",
        )

    if donation.status != DonationStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only available donations can be edited",
        )

    update_data = donation_data.model_dump(exclude_unset=True)

    prepared_at = update_data.get("prepared_at", donation.prepared_at)
    pickup_deadline = update_data.get(
        "pickup_deadline",
        donation.pickup_deadline,
    )

    validate_schedule(prepared_at, pickup_deadline)

    for key, value in update_data.items():
        setattr(donation, key, value)

    donation.updated_at = datetime.now(timezone.utc)

    db.add(donation)
    db.commit()
    db.refresh(donation)

    return donation


def cancel_donation(
    donation_id: int,
    restaurant: User,
    db: d_b.SessionDep,
) -> Donation:
    donation = get_donation_by_id(donation_id, db)

    if donation.restaurant_id != restaurant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this donation",
        )

    if donation.status != DonationStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only available donations can be cancelled",
        )

    donation.status = DonationStatus.CANCELLED
    donation.updated_at = datetime.now(timezone.utc)

    db.add(donation)

    add_status_history(
        db,
        donation_id=donation.id,
        actor_id=restaurant.id,
        entity_type=AuditEntityType.DONATION,
        action="DONATION_CANCELLED",
        old_status=DonationStatus.AVAILABLE.value,
        new_status=DonationStatus.CANCELLED.value,
    )

    db.commit()
    db.refresh(donation)

    return donation
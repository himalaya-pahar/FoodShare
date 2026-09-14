from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import select
from cache import invalidate_available_donations_cache

import database as d_b
import schemas
from models import AuditEntityType, Donation, DonationStatus, User, UserRole
from repository.status_history import add_status_history
from cache import (
    AVAILABLE_DONATIONS_TTL_SECONDS,
    get_available_donations_cache_key,
    get_cached_json,
    set_cached_json,
)


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
    invalidate_available_donations_cache()
    db.refresh(new_donation)

    return new_donation


def get_my_donations(
    current_user: User,
    db: d_b.SessionDep,
    limit: int,
    offset: int,
) -> schemas.PaginatedDonations:
    filters = []

    if current_user.role == UserRole.RESTAURANT:
        filters.append(Donation.restaurant_id == current_user.id)
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restaurant or Admin access required",
        )

    donations_statement = (
        select(Donation)
        .where(*filters)
        .order_by(Donation.created_at.asc(), Donation.id.asc())
        .offset(offset)
        .limit(limit)
    )

    total_statement = select(func.count(Donation.id)).where(*filters)

    donations = db.exec(donations_statement).all()
    total = db.exec(total_statement).one()

    return schemas.PaginatedDonations(
        items=donations,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_available_donations(
    db: d_b.SessionDep,
    area: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> schemas.PaginatedDonations:
    cache_key = get_available_donations_cache_key(
        area=area,
        limit=limit,
        offset=offset,
    )

    cached_data = get_cached_json(cache_key)

    if cached_data is not None:
        return schemas.PaginatedDonations.model_validate(
            cached_data
        )

    filters = [
        Donation.status == DonationStatus.AVAILABLE
    ]

    if area:
        filters.append(
            Donation.pickup_area == area.strip()
        )

    donations_statement = (
        select(Donation)
        .where(*filters)
        .order_by(Donation.pickup_deadline.asc(), Donation.id.asc())
        .offset(offset)
        .limit(limit)
    )

    total_statement = select(
        func.count(Donation.id)
    ).where(*filters)

    donations = db.exec(donations_statement).all()
    total = db.exec(total_statement).one()

    response = schemas.PaginatedDonations(
        items=donations,
        total=total,
        limit=limit,
        offset=offset,
    )

    set_cached_json(
        key=cache_key,
        value=response.model_dump(mode="json"),
        ttl_seconds=AVAILABLE_DONATIONS_TTL_SECONDS,
    )

    return response


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
    invalidate_available_donations_cache()
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
    invalidate_available_donations_cache()
    db.refresh(donation)

    return donation

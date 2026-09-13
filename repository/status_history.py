from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

import schemas
from models import (
    AuditEntityType,
    Donation,
    PickupRequest,
    StatusHistory,
    User,
    UserRole,
)


def add_status_history(
    db: Session,
    *,
    donation_id: int,
    actor_id: int,
    entity_type: AuditEntityType,
    action: str,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    pickup_request_id: Optional[int] = None,
    note: Optional[str] = None,
):
    history = StatusHistory(
        donation_id=donation_id,
        pickup_request_id=pickup_request_id,
        actor_id=actor_id,
        entity_type=entity_type,
        action=action,
        old_status=old_status,
        new_status=new_status,
        note=note,
    )

    db.add(history)


def get_my_donation_history(
    restaurant: User,
    db: Session,
) -> list[StatusHistory]:
    return db.exec(
        select(StatusHistory)
        .join(
            Donation,
            StatusHistory.donation_id == Donation.id,
        )
        .where(Donation.restaurant_id == restaurant.id)
        .order_by(StatusHistory.created_at.desc())
    ).all()


def get_donation_history(
    donation_id: int,
    current_user: User,
    db: Session,
    limit: int,
    offset: int,
) -> schemas.PaginatedStatusHistory:
    donation = db.get(Donation, donation_id)

    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation not found",
        )

    if (
        current_user.role != UserRole.ADMIN
        and donation.restaurant_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot view this donation history",
        )

    filters = [StatusHistory.donation_id == donation_id]

    history_statement = (
        select(StatusHistory)
        .where(*filters)
        .order_by(StatusHistory.created_at.desc(), StatusHistory.id.desc())
        .offset(offset)
        .limit(limit)
    )

    total_statement = select(func.count(StatusHistory.id)).where(*filters)

    history_items = db.exec(history_statement).all()
    total = db.exec(total_statement).one()

    return schemas.PaginatedStatusHistory(
        items=history_items,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_pickup_request_history(
    request_id: int,
    current_user: User,
    db: Session,
) -> list[StatusHistory]:
    pickup_request = db.get(PickupRequest, request_id)

    if not pickup_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pickup request not found",
        )

    donation = db.get(Donation, pickup_request.donation_id)

    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation not found",
        )

    is_ngo_owner = (
        current_user.role == UserRole.NGO
        and pickup_request.ngo_id == current_user.id
    )

    is_restaurant_owner = (
        current_user.role == UserRole.RESTAURANT
        and donation.restaurant_id == current_user.id
    )

    if (
        current_user.role != UserRole.ADMIN
        and not is_ngo_owner
        and not is_restaurant_owner
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot view this pickup request history",
        )

    return db.exec(
        select(StatusHistory)
        .where(StatusHistory.pickup_request_id == request_id)
        .order_by(StatusHistory.created_at.desc())
    ).all()


def get_my_pickup_history(
    current_user: User,
    db: Session,
    limit: int,
    offset: int,
) -> schemas.PaginatedStatusHistory:
    filters = []

    if current_user.role == UserRole.NGO:
        filters.append(PickupRequest.ngo_id == current_user.id)
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NGO or Admin access required",
        )

    history_statement = (
        select(StatusHistory)
        .join(
            PickupRequest,
            StatusHistory.pickup_request_id == PickupRequest.id,
        )
        .where(*filters)
        .order_by(StatusHistory.created_at.desc(), StatusHistory.id.desc())
        .offset(offset)
        .limit(limit)
    )

    total_statement = (
        select(func.count(StatusHistory.id))
        .join(
            PickupRequest,
            StatusHistory.pickup_request_id == PickupRequest.id,
        )
        .where(*filters)
    )

    history_items = db.exec(history_statement).all()
    total = db.exec(total_statement).one()

    return schemas.PaginatedStatusHistory(
        items=history_items,
        total=total,
        limit=limit,
        offset=offset,
    )

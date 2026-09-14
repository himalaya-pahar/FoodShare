from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from cache import invalidate_available_donations_cache

import database as d_b
import schemas
from models import (
    AuditEntityType,
    Donation,
    DonationStatus,
    PickupRequest,
    PickupRequestStatus,
    User,
    UserRole,
)
from repository.status_history import add_status_history


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def get_pickup_request(
    request_id: int,
    db: d_b.SessionDep,
) -> PickupRequest:
    pickup_request = db.get(PickupRequest, request_id)

    if not pickup_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pickup request not found",
        )

    return pickup_request


def get_owned_donation(
    donation_id: int,
    restaurant: User,
    db: d_b.SessionDep,
) -> Donation:
    donation = db.get(Donation, donation_id)

    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation not found",
        )

    if donation.restaurant_id != restaurant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this donation",
        )

    return donation


def get_viewable_donation(
    donation_id: int,
    current_user: User,
    db: d_b.SessionDep,
) -> Donation:
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
            detail="You cannot view pickup requests for this donation",
        )

    return donation


def create_pickup_request(
    donation_id: int,
    request_data: schemas.PickupRequestCreate,
    ngo: User,
    db: d_b.SessionDep,
) -> PickupRequest:
    donation = db.get(Donation, donation_id)

    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation not found",
        )

    if donation.status != DonationStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This donation is no longer available",
        )

    pickup_time = as_utc(request_data.estimated_pickup_at)

    available_from = max(
        as_utc(donation.prepared_at),
        as_utc(donation.created_at),
    )

    if pickup_time < available_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estimated pickup time must be after the donation was posted",
        )

    if pickup_time > as_utc(donation.pickup_deadline):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estimated pickup time must be before the pickup deadline",
        )

    existing_request = db.exec(
        select(PickupRequest).where(
            PickupRequest.donation_id == donation_id,
            PickupRequest.ngo_id == ngo.id,
        )
    ).first()

    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already requested this donation",
        )

    pickup_request = PickupRequest(
        donation_id=donation_id,
        ngo_id=ngo.id,
        estimated_pickup_at=pickup_time,
        message=request_data.message,
    )

    try:
        db.add(pickup_request)
        db.flush()

        add_status_history(
            db,
            donation_id=donation_id,
            pickup_request_id=pickup_request.id,
            actor_id=ngo.id,
            entity_type=AuditEntityType.PICKUP_REQUEST,
            action="PICKUP_REQUEST_CREATED",
            new_status=PickupRequestStatus.PENDING.value,
        )

        db.commit()
        db.refresh(pickup_request)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already requested this donation",
        )

    return pickup_request


def get_my_pickup_requests(
    current_user: User,
    db: d_b.SessionDep,
    limit: int,
    offset: int,
) -> schemas.PaginatedPickupRequests:
    filters = []

    if current_user.role == UserRole.NGO:
        filters.append(PickupRequest.ngo_id == current_user.id)
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NGO or Admin access required",
        )

    pickup_requests_statement = (
        select(PickupRequest)
        .where(*filters)
        .order_by(PickupRequest.requested_at.asc(), PickupRequest.id.asc())
        .offset(offset)
        .limit(limit)
    )

    total_statement = select(func.count(PickupRequest.id)).where(*filters)

    pickup_requests = db.exec(pickup_requests_statement).all()
    total = db.exec(total_statement).one()

    return schemas.PaginatedPickupRequests(
        items=pickup_requests,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_donation_pickup_requests(
    donation_id: int,
    current_user: User,
    db: d_b.SessionDep,
    limit: int,
    offset: int,
) -> schemas.PaginatedPickupRequests:
    get_viewable_donation(donation_id, current_user, db)

    filters = [PickupRequest.donation_id == donation_id]

    pickup_requests_statement = (
        select(PickupRequest)
        .where(*filters)
        .order_by(PickupRequest.requested_at.asc(), PickupRequest.id.asc())
        .offset(offset)
        .limit(limit)
    )

    total_statement = select(func.count(PickupRequest.id)).where(*filters)

    pickup_requests = db.exec(pickup_requests_statement).all()
    total = db.exec(total_statement).one()

    return schemas.PaginatedPickupRequests(
        items=pickup_requests,
        total=total,
        limit=limit,
        offset=offset,
    )


def accept_pickup_request(
    request_id: int,
    restaurant: User,
    db: d_b.SessionDep,
) -> PickupRequest:
    pickup_request = get_pickup_request(request_id, db)

    if pickup_request.status != PickupRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be accepted",
        )

    donation = get_owned_donation(
        pickup_request.donation_id,
        restaurant,
        db,
    )

    now = datetime.now(timezone.utc)

    reserve_donation = db.exec(
        update(Donation)
        .where(
            Donation.id == donation.id,
            Donation.status == DonationStatus.AVAILABLE,
        )
        .values(
            status=DonationStatus.RESERVED,
            updated_at=now,
        )
    )

    if reserve_donation.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This donation is no longer available",
        )

    pickup_request.status = PickupRequestStatus.ACCEPTED
    pickup_request.updated_at = now

    other_requests = db.exec(
        select(PickupRequest).where(
            PickupRequest.donation_id == donation.id,
            PickupRequest.id != pickup_request.id,
            PickupRequest.status == PickupRequestStatus.PENDING,
        )
    ).all()

    for other_request in other_requests:
        other_request.status = PickupRequestStatus.REJECTED
        other_request.updated_at = now
        db.add(other_request)

        add_status_history(
            db,
            donation_id=donation.id,
            pickup_request_id=other_request.id,
            actor_id=restaurant.id,
            entity_type=AuditEntityType.PICKUP_REQUEST,
            action="PICKUP_REQUEST_REJECTED",
            old_status=PickupRequestStatus.PENDING.value,
            new_status=PickupRequestStatus.REJECTED.value,
            note="Another pickup request was accepted",
        )

    db.add(pickup_request)

    add_status_history(
        db,
        donation_id=donation.id,
        pickup_request_id=pickup_request.id,
        actor_id=restaurant.id,
        entity_type=AuditEntityType.DONATION,
        action="DONATION_RESERVED",
        old_status=DonationStatus.AVAILABLE.value,
        new_status=DonationStatus.RESERVED.value,
    )

    add_status_history(
        db,
        donation_id=donation.id,
        pickup_request_id=pickup_request.id,
        actor_id=restaurant.id,
        entity_type=AuditEntityType.PICKUP_REQUEST,
        action="PICKUP_REQUEST_ACCEPTED",
        old_status=PickupRequestStatus.PENDING.value,
        new_status=PickupRequestStatus.ACCEPTED.value,
    )

    db.commit()
    invalidate_available_donations_cache()
    db.refresh(pickup_request)

    return pickup_request


def reject_pickup_request(
    request_id: int,
    restaurant: User,
    db: d_b.SessionDep,
) -> PickupRequest:
    pickup_request = get_pickup_request(request_id, db)

    if pickup_request.status != PickupRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be rejected",
        )

    get_owned_donation(
        pickup_request.donation_id,
        restaurant,
        db,
    )

    pickup_request.status = PickupRequestStatus.REJECTED
    pickup_request.updated_at = datetime.now(timezone.utc)

    db.add(pickup_request)

    add_status_history(
        db,
        donation_id=pickup_request.donation_id,
        pickup_request_id=pickup_request.id,
        actor_id=restaurant.id,
        entity_type=AuditEntityType.PICKUP_REQUEST,
        action="PICKUP_REQUEST_REJECTED",
        old_status=PickupRequestStatus.PENDING.value,
        new_status=PickupRequestStatus.REJECTED.value,
    )

    db.commit()
    db.refresh(pickup_request)

    return pickup_request


def withdraw_pickup_request(
    request_id: int,
    ngo: User,
    db: d_b.SessionDep,
) -> PickupRequest:
    pickup_request = get_pickup_request(request_id, db)

    if pickup_request.ngo_id != ngo.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this pickup request",
        )

    if pickup_request.status != PickupRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be withdrawn",
        )

    pickup_request.status = PickupRequestStatus.WITHDRAWN
    pickup_request.updated_at = datetime.now(timezone.utc)

    db.add(pickup_request)

    add_status_history(
        db,
        donation_id=pickup_request.donation_id,
        pickup_request_id=pickup_request.id,
        actor_id=ngo.id,
        entity_type=AuditEntityType.PICKUP_REQUEST,
        action="PICKUP_REQUEST_WITHDRAWN",
        old_status=PickupRequestStatus.PENDING.value,
        new_status=PickupRequestStatus.WITHDRAWN.value,
    )

    db.commit()
    db.refresh(pickup_request)

    return pickup_request


def mark_pickup_collected(
    request_id: int,
    ngo: User,
    db: d_b.SessionDep,
) -> PickupRequest:
    pickup_request = get_pickup_request(request_id, db)

    if pickup_request.ngo_id != ngo.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this pickup request",
        )

    if pickup_request.status != PickupRequestStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only accepted pickup requests can be collected",
        )

    donation = db.get(Donation, pickup_request.donation_id)

    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation not found",
        )

    if donation.status != DonationStatus.RESERVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This donation is not reserved",
        )

    now = datetime.now(timezone.utc)

    donation_result = db.exec(
        update(Donation)
        .where(
            Donation.id == donation.id,
            Donation.status == DonationStatus.RESERVED,
        )
        .values(
            status=DonationStatus.COLLECTED,
            updated_at=now,
        )
    )

    if donation_result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This donation cannot be marked as collected",
        )

    request_result = db.exec(
        update(PickupRequest)
        .where(
            PickupRequest.id == request_id,
            PickupRequest.ngo_id == ngo.id,
            PickupRequest.status == PickupRequestStatus.ACCEPTED,
        )
        .values(
            status=PickupRequestStatus.COLLECTED,
            updated_at=now,
        )
    )

    if request_result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This pickup request cannot be marked as collected",
        )

    add_status_history(
        db,
        donation_id=donation.id,
        pickup_request_id=pickup_request.id,
        actor_id=ngo.id,
        entity_type=AuditEntityType.DONATION,
        action="DONATION_COLLECTED",
        old_status=DonationStatus.RESERVED.value,
        new_status=DonationStatus.COLLECTED.value,
    )

    add_status_history(
        db,
        donation_id=donation.id,
        pickup_request_id=pickup_request.id,
        actor_id=ngo.id,
        entity_type=AuditEntityType.PICKUP_REQUEST,
        action="PICKUP_REQUEST_COLLECTED",
        old_status=PickupRequestStatus.ACCEPTED.value,
        new_status=PickupRequestStatus.COLLECTED.value,
    )

    db.commit()
    invalidate_available_donations_cache()
    db.refresh(pickup_request)

    return pickup_request


def complete_donation(
    donation_id: int,
    restaurant: User,
    db: d_b.SessionDep,
) -> Donation:
    donation = get_owned_donation(
        donation_id,
        restaurant,
        db,
    )

    if donation.status != DonationStatus.COLLECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only collected donations can be completed",
        )

    collected_request = db.exec(
        select(PickupRequest).where(
            PickupRequest.donation_id == donation_id,
            PickupRequest.status == PickupRequestStatus.COLLECTED,
        )
    ).first()

    if not collected_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No collected pickup request found",
        )

    result = db.exec(
        update(Donation)
        .where(
            Donation.id == donation_id,
            Donation.status == DonationStatus.COLLECTED,
        )
        .values(
            status=DonationStatus.COMPLETED,
            updated_at=datetime.now(timezone.utc),
        )
    )

    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This donation cannot be completed",
        )

    add_status_history(
        db,
        donation_id=donation.id,
        pickup_request_id=collected_request.id,
        actor_id=restaurant.id,
        entity_type=AuditEntityType.DONATION,
        action="DONATION_COMPLETED",
        old_status=DonationStatus.COLLECTED.value,
        new_status=DonationStatus.COMPLETED.value,
    )

    db.commit()
    invalidate_available_donations_cache()
    db.refresh(donation)

    return donation

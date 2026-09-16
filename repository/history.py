from collections import defaultdict
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import select

import database as d_b
import schemas
from models import (
    AuditEntityType,
    Donation,
    DonationStatus,
    PickupRequest,
    PickupRequestStatus,
    StatusHistory,
    User,
    UserRole,
)


def _organization_name(user: User | None) -> str | None:
    if not user:
        return None

    if user.organization_name and user.organization_name.strip():
        return user.organization_name.strip()

    return user.full_name


def _get_users_by_id(
    user_ids: set[int],
    db: d_b.SessionDep,
) -> dict[int, User]:
    if not user_ids:
        return {}

    users = db.exec(
        select(User).where(User.id.in_(user_ids))
    ).all()

    return {
        user.id: user
        for user in users
        if user.id is not None
    }


def _get_timestamps_by_entity_id(
    history_rows: list[StatusHistory],
    entity_id_attribute: str,
) -> dict[int, dict[str, datetime]]:
    timestamps_by_entity_id: dict[int, dict[str, datetime]] = defaultdict(dict)

    for history in history_rows:
        entity_id = getattr(history, entity_id_attribute)

        if (
            entity_id is not None
            and history.new_status
            and history.new_status
            not in timestamps_by_entity_id[entity_id]
        ):
            timestamps_by_entity_id[entity_id][history.new_status] = (
                history.created_at
            )

    return timestamps_by_entity_id


def get_donation_journeys(
    current_user: User,
    db: d_b.SessionDep,
    limit: int,
    offset: int,
) -> schemas.PaginatedHistoryFlows:
    filters = []

    if current_user.role == UserRole.RESTAURANT:
        filters.append(Donation.restaurant_id == current_user.id)
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restaurant or Admin access required",
        )

    total = db.exec(
        select(func.count(Donation.id)).where(*filters)
    ).one()

    donations = db.exec(
        select(Donation)
        .where(*filters)
        .order_by(Donation.created_at.desc(), Donation.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    donation_ids = [
        donation.id
        for donation in donations
        if donation.id is not None
    ]

    if not donation_ids:
        return schemas.PaginatedHistoryFlows(
            items=[],
            total=total,
            limit=limit,
            offset=offset,
        )

    selected_requests = db.exec(
        select(PickupRequest)
        .where(
            PickupRequest.donation_id.in_(donation_ids),
            PickupRequest.status.in_(
                [
                    PickupRequestStatus.ACCEPTED,
                    PickupRequestStatus.COLLECTED,
                ]
            ),
        )
        .order_by(
            PickupRequest.updated_at.desc(),
            PickupRequest.id.desc(),
        )
    ).all()

    selected_request_by_donation_id: dict[int, PickupRequest] = {}
    for pickup_request in selected_requests:
        selected_request_by_donation_id.setdefault(
            pickup_request.donation_id,
            pickup_request,
        )

    donation_history_rows = db.exec(
        select(StatusHistory)
        .where(
            StatusHistory.donation_id.in_(donation_ids),
            StatusHistory.entity_type == AuditEntityType.DONATION,
        )
        .order_by(StatusHistory.created_at.asc(), StatusHistory.id.asc())
    ).all()
    donation_timestamps = _get_timestamps_by_entity_id(
        donation_history_rows,
        "donation_id",
    )

    user_ids = {
        donation.restaurant_id
        for donation in donations
    }
    user_ids.update(
        pickup_request.ngo_id
        for pickup_request in selected_request_by_donation_id.values()
    )
    users_by_id = _get_users_by_id(user_ids, db)

    items = []
    for donation in donations:
        selected_request = selected_request_by_donation_id.get(donation.id)
        timestamps = dict(donation_timestamps.get(donation.id, {}))
        timestamps.setdefault("AVAILABLE", donation.created_at)

        donor_name = _organization_name(
            users_by_id.get(donation.restaurant_id)
        ) or "Unknown restaurant"
        receiver_name = (
            _organization_name(users_by_id.get(selected_request.ngo_id))
            if selected_request
            else None
        )

        items.append(
            schemas.HistoryFlow(
                donation_id=donation.id,
                pickup_request_id=(
                    selected_request.id if selected_request else None
                ),
                food_name=donation.food_name,
                posted_at=donation.created_at,
                donor_organization_name=donor_name,
                receiver_organization_name=receiver_name,
                current_status=donation.status.value,
                status_timestamps=timestamps,
            )
        )

    return schemas.PaginatedHistoryFlows(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_pickup_journeys(
    current_user: User,
    db: d_b.SessionDep,
    limit: int,
    offset: int,
) -> schemas.PaginatedHistoryFlows:
    filters = []

    if current_user.role == UserRole.NGO:
        filters.append(PickupRequest.ngo_id == current_user.id)
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NGO or Admin access required",
        )

    total = db.exec(
        select(func.count(PickupRequest.id)).where(*filters)
    ).one()

    pickup_requests = db.exec(
        select(PickupRequest)
        .where(*filters)
        .order_by(PickupRequest.requested_at.desc(), PickupRequest.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    request_ids = [
        pickup_request.id
        for pickup_request in pickup_requests
        if pickup_request.id is not None
    ]
    donation_ids = [
        pickup_request.donation_id
        for pickup_request in pickup_requests
    ]

    if not request_ids:
        return schemas.PaginatedHistoryFlows(
            items=[],
            total=total,
            limit=limit,
            offset=offset,
        )

    donations = db.exec(
        select(Donation).where(Donation.id.in_(donation_ids))
    ).all()
    donations_by_id = {
        donation.id: donation
        for donation in donations
        if donation.id is not None
    }

    pickup_history_rows = db.exec(
        select(StatusHistory)
        .where(
            StatusHistory.pickup_request_id.in_(request_ids),
            StatusHistory.entity_type == AuditEntityType.PICKUP_REQUEST,
        )
        .order_by(StatusHistory.created_at.asc(), StatusHistory.id.asc())
    ).all()
    pickup_timestamps = _get_timestamps_by_entity_id(
        pickup_history_rows,
        "pickup_request_id",
    )

    completion_history_rows = db.exec(
        select(StatusHistory)
        .where(
            StatusHistory.donation_id.in_(donation_ids),
            StatusHistory.entity_type == AuditEntityType.DONATION,
            StatusHistory.new_status == DonationStatus.COMPLETED.value,
        )
        .order_by(StatusHistory.created_at.asc(), StatusHistory.id.asc())
    ).all()
    completion_timestamps = {
        donation_id: timestamps[DonationStatus.COMPLETED.value]
        for donation_id, timestamps in _get_timestamps_by_entity_id(
            completion_history_rows,
            "donation_id",
        ).items()
        if DonationStatus.COMPLETED.value in timestamps
    }

    user_ids = {
        pickup_request.ngo_id
        for pickup_request in pickup_requests
    }
    user_ids.update(
        donation.restaurant_id
        for donation in donations
    )
    users_by_id = _get_users_by_id(user_ids, db)

    items = []
    for pickup_request in pickup_requests:
        donation = donations_by_id.get(pickup_request.donation_id)

        if not donation:
            continue

        timestamps = dict(pickup_timestamps.get(pickup_request.id, {}))
        timestamps.setdefault("PENDING", pickup_request.requested_at)

        if pickup_request.status in (
            PickupRequestStatus.REJECTED,
            PickupRequestStatus.WITHDRAWN,
        ):
            current_status = pickup_request.status.value
        elif donation.status == DonationStatus.COMPLETED:
            current_status = DonationStatus.COMPLETED.value
            completed_at = completion_timestamps.get(donation.id)
            if completed_at:
                timestamps.setdefault(DonationStatus.COMPLETED.value, completed_at)
        else:
            current_status = pickup_request.status.value

        donor_name = _organization_name(
            users_by_id.get(donation.restaurant_id)
        ) or "Unknown restaurant"
        receiver_name = _organization_name(
            users_by_id.get(pickup_request.ngo_id)
        ) or "Unknown NGO"

        items.append(
            schemas.HistoryFlow(
                donation_id=donation.id,
                pickup_request_id=pickup_request.id,
                food_name=donation.food_name,
                posted_at=donation.created_at,
                donor_organization_name=donor_name,
                receiver_organization_name=receiver_name,
                current_status=current_status,
                status_timestamps=timestamps,
            )
        )

    return schemas.PaginatedHistoryFlows(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlmodel import select

import database as d_b
import schemas
from models import ApprovalStatus, User, UserRole, Donation, PickupRequest, StatusHistory


def _user_search_filters(q: str | None) -> list:
    if not q or not q.strip():
        return []

    pattern = f"%{q.strip()}%"

    return [
        or_(
            User.full_name.ilike(pattern),
            User.email.ilike(pattern),
            User.organization_name.ilike(pattern),
        )
    ]


def _get_paginated_users(
    db: d_b.SessionDep,
    limit: int,
    offset: int,
    q: str | None = None,
    pending_only: bool = False,
) -> schemas.PaginatedUsers:
    filters = _user_search_filters(q)

    if pending_only:
        filters.extend(
            [
                User.approval_status == ApprovalStatus.PENDING,
                User.role.in_([UserRole.RESTAURANT, UserRole.NGO]),
            ]
        )

    users_statement = (
        select(User)
        .where(*filters)
        .order_by(User.created_at.desc(), User.id.desc())
        .offset(offset)
        .limit(limit)
    )

    total_statement = select(func.count(User.id)).where(*filters)

    users = db.exec(users_statement).all()
    total = db.exec(total_statement).one()

    return schemas.PaginatedUsers(
        items=users,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_pending_users(
    db: d_b.SessionDep,
    limit: int,
    offset: int,
    q: str | None = None,
) -> schemas.PaginatedUsers:
    return _get_paginated_users(
        db=db,
        limit=limit,
        offset=offset,
        q=q,
        pending_only=True,
    )


def update_approval_status(
    user_id: int,
    new_status: ApprovalStatus,
    db: d_b.SessionDep,
) -> User:
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot be changed here",
        )

    if user.approval_status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has already been reviewed",
        )

    if new_status not in (
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose APPROVED or REJECTED",
        )

    user.approval_status = new_status
    user.updated_at = datetime.now(timezone.utc)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_all_users(
    db: d_b.SessionDep,
    limit: int,
    offset: int,
    q: str | None = None,
) -> schemas.PaginatedUsers:
    return _get_paginated_users(
        db=db,
        limit=limit,
        offset=offset,
        q=q,
    )


def get_admin_stats(
    db: d_b.SessionDep,
) -> schemas.AdminStats:
    statement = select(
        func.count(User.id),
        func.count(User.id).filter(
            User.approval_status == ApprovalStatus.PENDING
        ),
        func.count(User.id).filter(
            User.approval_status == ApprovalStatus.APPROVED
        ),
        func.count(User.id).filter(User.role == UserRole.RESTAURANT),
        func.count(User.id).filter(User.role == UserRole.NGO),
    )

    total, pending, approved, restaurants, ngos = db.exec(statement).one()

    return schemas.AdminStats(
        total_users=total,
        pending_users=pending,
        approved_users=approved,
        restaurant_users=restaurants,
        ngo_users=ngos,
    )


def delete_user(user_id: int, db: d_b.SessionDep):
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot be deleted",
        )

    has_donation = db.exec(
        select(Donation.id).where(Donation.restaurant_id == user_id)
    ).first()

    has_pickup_request = db.exec(
        select(PickupRequest.id).where(PickupRequest.ngo_id == user_id)
    ).first()

    has_history = db.exec(
        select(StatusHistory.id).where(StatusHistory.actor_id == user_id)
    ).first()

    if has_donation or has_pickup_request or has_history:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a user with activity. Reject the account instead.",
        )

    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully"}

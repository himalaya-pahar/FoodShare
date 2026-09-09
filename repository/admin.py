from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import select

import database as d_b
from models import ApprovalStatus, User, UserRole, Donation, PickupRequest, StatusHistory


def get_pending_users(db: d_b.SessionDep) -> list[User]:
    return db.exec(
        select(User)
        .where(User.approval_status == ApprovalStatus.PENDING)
        .where(User.role.in_([UserRole.RESTAURANT, UserRole.NGO]))
        .order_by(User.created_at)
    ).all()


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


def get_all_users(db: d_b.SessionDep) -> list[User]:
    return db.exec(
        select(User).order_by(User.created_at)
    ).all()


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
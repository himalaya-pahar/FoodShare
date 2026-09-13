from fastapi import APIRouter, Query

import database as d_b
import schemas
from repository import admin as admin_repository
from security.oauth2 import AdminDep


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get(
    "/users/pending",
    response_model=schemas.PaginatedUsers,
)
def list_pending_users(
    db: d_b.SessionDep,
    current_admin: AdminDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=100),
):
    return admin_repository.get_pending_users(
        db=db,
        limit=limit,
        offset=offset,
        q=q,
    )


@router.patch(
    "/users/{user_id}/approval",
    response_model=schemas.AdminUserItem,
)
def update_user_approval(
    user_id: int,
    approval: schemas.ApprovalUpdate,
    db: d_b.SessionDep,
    current_admin: AdminDep,
):
    return admin_repository.update_approval_status(
        user_id=user_id,
        new_status=approval.approval_status,
        db=db,
    )


@router.get(
    "/users",
    response_model=schemas.PaginatedUsers,
)
def list_all_users(
    db: d_b.SessionDep,
    current_admin: AdminDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=100),
):
    return admin_repository.get_all_users(
        db=db,
        limit=limit,
        offset=offset,
        q=q,
    )


@router.get(
    "/stats",
    response_model=schemas.AdminStats,
)
def get_admin_stats(
    db: d_b.SessionDep,
    current_admin: AdminDep,
):
    return admin_repository.get_admin_stats(db)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: d_b.SessionDep,
    current_admin: AdminDep,
):
    return admin_repository.delete_user(user_id, db)

from fastapi import APIRouter

import database as d_b
import schemas
from repository import status_history as history_repository
from security import oauth2


router = APIRouter(
    tags=["Status History"],
)


@router.get(
    "/donations/my/history",
    response_model=list[schemas.ShowStatusHistory],
)
def my_donation_history(
    db: d_b.SessionDep,
    restaurant: oauth2.RestaurantDep,
):
    return history_repository.get_my_donation_history(
        restaurant,
        db,
    )


@router.get(
    "/donations/{donation_id}/history",
    response_model=list[schemas.ShowStatusHistory],
)
def donation_history(
    donation_id: int,
    db: d_b.SessionDep,
    current_user: oauth2.CurrentUserDep,
):
    return history_repository.get_donation_history(
        donation_id,
        current_user,
        db,
    )


@router.get(
    "/pickup-requests/my/history",
    response_model=list[schemas.ShowStatusHistory],
)
def my_pickup_history(
    db: d_b.SessionDep,
    ngo: oauth2.NGODep,
):
    return history_repository.get_my_pickup_history(
        ngo,
        db,
    )


@router.get(
    "/pickup-requests/{request_id}/history",
    response_model=list[schemas.ShowStatusHistory],
)
def pickup_request_history(
    request_id: int,
    db: d_b.SessionDep,
    current_user: oauth2.CurrentUserDep,
):
    return history_repository.get_pickup_request_history(
        request_id,
        current_user,
        db,
    )
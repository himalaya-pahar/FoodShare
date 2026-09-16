from fastapi import APIRouter, Query

import database as d_b
import schemas
from repository import history as history_repository
from security import oauth2


router = APIRouter(
    prefix="/history",
    tags=["Journey History"],
)


@router.get(
    "/donations",
    response_model=schemas.PaginatedHistoryFlows,
)
def donation_journey_history(
    db: d_b.SessionDep,
    current_user: oauth2.RestaurantOrAdminDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return history_repository.get_donation_journeys(
        current_user=current_user,
        db=db,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/pickups",
    response_model=schemas.PaginatedHistoryFlows,
)
def pickup_journey_history(
    db: d_b.SessionDep,
    current_user: oauth2.NGOOrAdminDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return history_repository.get_pickup_journeys(
        current_user=current_user,
        db=db,
        limit=limit,
        offset=offset,
    )

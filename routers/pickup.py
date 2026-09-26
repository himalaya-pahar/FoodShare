from fastapi import APIRouter, Query, status

import database as d_b
import schemas
from repository import pickup as pickup_repository
from security import oauth2


router = APIRouter(
    tags=["Pickup Requests"],
)


@router.post(
    "/donations/{donation_id}/pickup-requests",
    response_model=schemas.ShowPickupRequest,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/donations/{donation_id}/requests",
    response_model=schemas.ShowPickupRequest,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_pickup_request(
    donation_id: int,
    pickup_request: schemas.PickupRequestCreate,
    db: d_b.SessionDep,
    ngo: oauth2.NGODep,
):
    return pickup_repository.create_pickup_request(
        donation_id,
        pickup_request,
        ngo,
        db,
    )


@router.get(
    "/pickup-requests/my",
    response_model=schemas.PaginatedPickupRequests,
)
@router.get(
    "/pickups/my",
    response_model=schemas.PaginatedPickupRequests,
    include_in_schema=False,
)
def get_my_pickup_requests(
    db: d_b.SessionDep,
    current_user: oauth2.NGOOrAdminDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return pickup_repository.get_my_pickup_requests(
        current_user=current_user,
        db=db,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/donations/{donation_id}/pickup-requests",
    response_model=schemas.PaginatedDonationPickupRequests,
)
@router.get(
    "/donations/{donation_id}/requests",
    response_model=schemas.PaginatedDonationPickupRequests,
    include_in_schema=False,
)
def get_donation_pickup_requests(
    donation_id: int,
    db: d_b.SessionDep,
    current_user: oauth2.RestaurantOrAdminDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return pickup_repository.get_donation_pickup_requests(
        donation_id=donation_id,
        current_user=current_user,
        db=db,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/pickup-requests/{request_id}/accept",
    response_model=schemas.ShowPickupRequest,
)
def accept_pickup_request(
    request_id: int,
    db: d_b.SessionDep,
    restaurant: oauth2.RestaurantDep,
):
    return pickup_repository.accept_pickup_request(
        request_id,
        restaurant,
        db,
    )


@router.post(
    "/pickup-requests/{request_id}/reject",
    response_model=schemas.ShowPickupRequest,
)
def reject_pickup_request(
    request_id: int,
    db: d_b.SessionDep,
    restaurant: oauth2.RestaurantDep,
):
    return pickup_repository.reject_pickup_request(
        request_id,
        restaurant,
        db,
    )


@router.post(
    "/pickup-requests/{request_id}/withdraw",
    response_model=schemas.ShowPickupRequest,
)
def withdraw_pickup_request(
    request_id: int,
    db: d_b.SessionDep,
    ngo: oauth2.NGODep,
):
    return pickup_repository.withdraw_pickup_request(
        request_id,
        ngo,
        db,
    )


@router.post(
    "/pickup-requests/{request_id}/collect",
    response_model=schemas.ShowPickupRequest,
)
def mark_pickup_collected(
    request_id: int,
    db: d_b.SessionDep,
    ngo: oauth2.NGODep,
):
    return pickup_repository.mark_pickup_collected(
        request_id,
        ngo,
        db,
    )



@router.post(
    "/donations/{donation_id}/complete",
    response_model=schemas.ShowDonation,
)
def complete_donation(
    donation_id: int,
    db: d_b.SessionDep,
    restaurant: oauth2.RestaurantDep,
):
    return pickup_repository.complete_donation(
        donation_id,
        restaurant,
        db,
    )

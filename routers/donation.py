from typing import Optional

from fastapi import APIRouter, status

import database as d_b
import schemas
from repository import donation as donation_repository
from security import oauth2


router = APIRouter(
    prefix="/donations",
    tags=["Donations"],
)


@router.post(
    "/",
    response_model=schemas.ShowDonation,
    status_code=status.HTTP_201_CREATED,
)
def create_donation(
    donation: schemas.DonationCreate,
    db: d_b.SessionDep,
    restaurant: oauth2.RestaurantDep,
):
    return donation_repository.create_donation(
        donation,
        restaurant,
        db,
    )


@router.get(
    "/my",
    response_model=list[schemas.ShowDonation],
)
def get_my_donations(
    db: d_b.SessionDep,
    restaurant: oauth2.RestaurantDep,
):
    return donation_repository.get_my_donations(
        restaurant,
        db,
    )


@router.get(
    "/available",
    response_model=list[schemas.ShowDonation],
)
def get_available_donations(
    db: d_b.SessionDep,
    ngo: oauth2.NGODep,
    area: Optional[str] = None,
):
    return donation_repository.get_available_donations(
        db,
        area,
    )


@router.get(
    "/{donation_id}",
    response_model=schemas.ShowDonation,
)
def get_donation(
    donation_id: int,
    db: d_b.SessionDep,
    current_user: oauth2.CurrentUserDep,
):
    return donation_repository.get_donation_by_id(
        donation_id,
        db,
    )


@router.patch(
    "/{donation_id}",
    response_model=schemas.ShowDonation,
)
def update_donation(
    donation_id: int,
    donation: schemas.DonationUpdate,
    db: d_b.SessionDep,
    restaurant: oauth2.RestaurantDep,
):
    return donation_repository.update_donation(
        donation_id,
        donation,
        restaurant,
        db,
    )


@router.post(
    "/{donation_id}/cancel",
    response_model=schemas.ShowDonation,
)
def cancel_donation(
    donation_id: int,
    db: d_b.SessionDep,
    restaurant: oauth2.RestaurantDep,
):
    return donation_repository.cancel_donation(
        donation_id,
        restaurant,
        db,
    )
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

import database as d_b
import schemas
from models import User, UserRole
from repository import donation_media
from security.oauth2 import get_current_user


router = APIRouter(
    tags=["Donation Media"],
)

CurrentUser = Annotated[User, Depends(get_current_user)]


def require_restaurant(
    current_user: CurrentUser,
) -> User:
    if current_user.role != UserRole.RESTAURANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only restaurants can manage donation media",
        )

    return current_user


RestaurantUser = Annotated[User, Depends(require_restaurant)]


@router.post(
    "/donations/{donation_id}/media/upload-url",
    response_model=schemas.DonationMediaUploadUrl,
    status_code=status.HTTP_201_CREATED,
)
def request_upload_url(
    donation_id: int,
    upload_data: schemas.DonationMediaUploadRequest,
    restaurant: RestaurantUser,
    db: d_b.SessionDep,
):
    return donation_media.request_donation_media_upload(
        donation_id,
        upload_data,
        restaurant,
        db,
    )


@router.post(
    "/donation-media/{media_id}/complete",
    response_model=schemas.ShowDonationMedia,
)
def complete_upload(
    media_id: int,
    restaurant: RestaurantUser,
    db: d_b.SessionDep,
):
    return donation_media.complete_donation_media_upload(
        media_id,
        restaurant,
        db,
    )


@router.get(
    "/donations/{donation_id}/media",
    response_model=list[schemas.ShowDonationMedia],
)
def get_media(
    donation_id: int,
    current_user: CurrentUser,
    db: d_b.SessionDep,
):
    return donation_media.get_donation_media(
        donation_id,
        db,
    )


@router.delete(
    "/donation-media/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_media(
    media_id: int,
    restaurant: RestaurantUser,
    db: d_b.SessionDep,
):
    donation_media.delete_donation_media(
        media_id,
        restaurant,
        db,
    )
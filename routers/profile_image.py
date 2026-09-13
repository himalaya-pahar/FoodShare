from typing import Annotated

from fastapi import APIRouter, Depends, status

import database as d_b
import schemas
from models import User
from repository import profile_image
from security.oauth2 import get_current_user


router = APIRouter(
    prefix="/profile-image",
    tags=["Profile Image"],
)

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/upload-url",
    response_model=schemas.ProfileImageUploadUrl,
    status_code=status.HTTP_201_CREATED,
)
def request_upload_url(
    upload_data: schemas.ProfileImageUploadRequest,
    current_user: CurrentUser,
    db: d_b.SessionDep,
):
    return profile_image.request_profile_image_upload(
        upload_data,
        current_user,
        db,
    )


@router.post(
    "/{image_id}/complete",
    response_model=schemas.ShowUserProfileImage,
)
def complete_upload(
    image_id: int,
    current_user: CurrentUser,
    db: d_b.SessionDep,
):
    return profile_image.complete_profile_image_upload(
        image_id,
        current_user,
        db,
    )


@router.get(
    "/me",
    response_model=schemas.ShowUserProfileImage | None,
)
def get_my_image(
    current_user: CurrentUser,
    db: d_b.SessionDep,
):
    return profile_image.get_my_profile_image(
        current_user,
        db,
    )


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_my_image(
    image_id: int,
    current_user: CurrentUser,
    db: d_b.SessionDep,
):
    profile_image.delete_my_profile_image(
        image_id,
        current_user,
        db,
    )
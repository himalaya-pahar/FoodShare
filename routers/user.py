from typing import Annotated

from fastapi import APIRouter, Depends

import database as d_b
import schemas
from models import User
from repository import user as user_repository
from security.oauth2 import get_current_user


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/me", response_model=schemas.ShowUser)
def get_me(
    current_user: CurrentUser,
) -> schemas.ShowUser:
    return current_user


@router.patch("/me", response_model=schemas.ShowUser)
def update_me(
    profile_data: schemas.UserProfileUpdate,
    db: d_b.SessionDep,
    current_user: CurrentUser,
) -> schemas.ShowUser:
    return user_repository.update_my_profile(
        profile_data=profile_data,
        current_user=current_user,
        db=db,
    )

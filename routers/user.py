from typing import Annotated

from fastapi import APIRouter, Depends

import schemas
from models import User
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
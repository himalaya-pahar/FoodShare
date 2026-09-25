from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select

import database as d_b
from models import ApprovalStatus, User, UserRole, UserStatus
from security import token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_current_user(
    db: d_b.SessionDep,
    data: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_email = token.verify_token(data, credentials_exception)

    user = db.exec(
        select(User).where(User.email == user_email)
    ).first()

    if not user:
        raise credentials_exception

    if user.status != UserStatus.ACTIVE:
        if user.status == UserStatus.PENDING_EMAIL:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your email is not verified yet. Please check your email to verify your account.",
            )
        elif user.status == UserStatus.PENDING_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is pending admin approval.",
            )
        elif user.status == UserStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been rejected by an administrator.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not approved yet.",
            )

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_current_admin(current_user: CurrentUserDep) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


AdminDep = Annotated[User, Depends(get_current_admin)]


def get_current_restaurant(current_user: CurrentUserDep) -> User:
    if current_user.role != UserRole.RESTAURANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restaurant access required",
        )

    return current_user


RestaurantDep = Annotated[User, Depends(get_current_restaurant)]


def get_current_ngo(current_user: CurrentUserDep) -> User:
    if current_user.role != UserRole.NGO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NGO access required",
        )

    return current_user


NGODep = Annotated[User, Depends(get_current_ngo)]


def get_current_restaurant_or_admin(
    current_user: CurrentUserDep,
) -> User:
    if current_user.role not in (UserRole.RESTAURANT, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restaurant or Admin access required",
        )

    return current_user


RestaurantOrAdminDep = Annotated[
    User,
    Depends(get_current_restaurant_or_admin),
]


def get_current_ngo_or_admin(
    current_user: CurrentUserDep,
) -> User:
    if current_user.role not in (UserRole.NGO, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NGO or Admin access required",
        )

    return current_user


NGOOrAdminDep = Annotated[
    User,
    Depends(get_current_ngo_or_admin),
]

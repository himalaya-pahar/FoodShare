from fastapi import Depends,HTTPException,status
from fastapi.security import OAuth2PasswordRequestForm
import schemas,database as d_b
from security import hashing,token
from typing import Annotated
from sqlmodel import select

from fastapi import HTTPException, status
from sqlmodel import select

import database as d_b
import schemas
from models import User, UserRole, ApprovalStatus
from security import hashing


def signup(user: schemas.UserSignup, db: d_b.SessionDep) -> schemas.ShowUser:
    existing_user = db.exec(
        select(User).where(User.email == user.email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot be created through signup",
        )

    new_user = User(
        full_name=user.full_name,
        organization_name=user.organization_name,
        email=user.email.lower().strip(),
        password_hash=hashing.get_hash_password(user.password),
        role=user.role,
        phone=user.phone,
        address=user.address,
        area=user.area,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

def signin(
    user: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: d_b.SessionDep,
):
    find_user = db.exec(
        select(User).where(User.email == user.username.lower().strip())
    ).first()

    if not find_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not hashing.verify_password(user.password, find_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if find_user.approval_status != ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending admin approval",
        )

    access_token = token.create_access_token(
        data={"sub": find_user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

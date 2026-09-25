from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm

import database as d_b
from repository import authenticate as repo_auth
import schemas

router = APIRouter(
    tags=["Authentication & Email Verification"],
)


@router.post(
    "/signup",
    response_model=schemas.ShowUser,
    status_code=201,
)
@router.post(
    "/auth/signup",
    response_model=schemas.ShowUser,
    status_code=201,
    include_in_schema=False,
)
def signup(
    user: schemas.UserSignup,
    db: d_b.SessionDep,
) -> schemas.ShowUser:
    return repo_auth.signup(user, db)


@router.post("/login")
@router.post("/auth/login", include_in_schema=False)
def signin(
    user: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: d_b.SessionDep,
):
    return repo_auth.signin(user, db)


@router.get(
    "/auth/verify-email",
    response_model=schemas.VerifyEmailResponse,
)
@router.get(
    "/verify-email",
    response_model=schemas.VerifyEmailResponse,
    include_in_schema=False,
)
def verify_email(
    token: str = Query(..., description="Raw email verification token"),
    db: d_b.SessionDep = None,
) -> schemas.VerifyEmailResponse:
    return repo_auth.verify_email(token_str=token, db=db)


@router.post(
    "/auth/resend-verification",
    response_model=schemas.ResendVerificationResponse,
)
@router.post(
    "/resend-verification",
    response_model=schemas.ResendVerificationResponse,
    include_in_schema=False,
)
def resend_verification(
    request_data: schemas.ResendVerificationRequest,
    db: d_b.SessionDep,
) -> schemas.ResendVerificationResponse:
    return repo_auth.resend_verification(request_data=request_data, db=db)

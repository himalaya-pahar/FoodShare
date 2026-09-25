from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

import database as d_b
from repository import authenticate as repo_auth
import schemas
from services.email import (
    render_verification_error_html,
    render_verification_success_html,
)

router = APIRouter(
    tags=["Authentication & Email Verification"],
)


def _extract_base_url(request: Request) -> str:
    """Extracts client-facing base URL considering reverse proxies / Vercel."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme or "https")
    host = request.headers.get(
        "x-forwarded-host",
        request.headers.get("host", request.url.netloc or ""),
    )
    if host:
        return f"{proto}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")


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
    request: Request,
) -> schemas.ShowUser:
    base_url = _extract_base_url(request)
    return repo_auth.signup(user=user, db=db, request_base_url=base_url)


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
    request: Request,
    token: str = Query(..., description="Raw email verification token"),
    db: d_b.SessionDep = None,
):
    accept_header = request.headers.get("accept", "")
    wants_html = "text/html" in accept_header

    try:
        result = repo_auth.verify_email(token_str=token, db=db)
        if wants_html:
            return HTMLResponse(
                content=render_verification_success_html(
                    message=result.message,
                    status=result.status.value if hasattr(result.status, "value") else str(result.status),
                ),
                status_code=200,
            )
        return result
    except HTTPException as exc:
        if wants_html:
            status_code = exc.status_code if exc.status_code in (400, 404) else 400
            return HTMLResponse(
                content=render_verification_error_html(
                    error_message=str(exc.detail),
                ),
                status_code=status_code,
            )
        raise exc


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
    request: Request,
) -> schemas.ResendVerificationResponse:
    base_url = _extract_base_url(request)
    return repo_auth.resend_verification(
        request_data=request_data,
        db=db,
        request_base_url=base_url,
    )

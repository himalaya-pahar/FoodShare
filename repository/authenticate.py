from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from config import (
    VERIFICATION_RESEND_COOLDOWN_SECONDS,
    VERIFICATION_TOKEN_EXPIRE_HOURS,
    VERIFICATION_TOKEN_EXPIRE_MINUTES,
)
import database as d_b
from models import ApprovalStatus, User, UserRole, UserStatus, utc_now
import schemas
from security import hashing, token
from security.verification import (
    generate_verification_token,
    hash_verification_token,
)
from services.email import email_service


def signup(
    user: schemas.UserSignup,
    db: d_b.SessionDep,
    request_base_url: str | None = None,
) -> schemas.ShowUser:
    email_clean = user.email.lower().strip()

    existing_user = db.exec(
        select(User).where(User.email == email_clean)
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

    # Generate cryptographically secure single-use verification token
    raw_token, token_hash = generate_verification_token()
    now = utc_now()
    expires_at = now + timedelta(minutes=VERIFICATION_TOKEN_EXPIRE_MINUTES)

    new_user = User(
        full_name=user.full_name.strip(),
        organization_name=user.organization_name.strip() if user.organization_name else None,
        email=email_clean,
        password_hash=hashing.get_hash_password(user.password),
        role=user.role,
        status=UserStatus.PENDING_EMAIL,
        email_verified=False,
        email_verified_at=None,
        verification_token_hash=token_hash,
        last_verification_sent_at=now,
        verification_token_expires_at=expires_at,
        approval_status=ApprovalStatus.PENDING,
        phone=user.phone.strip() if user.phone else None,
        address=user.address.strip() if user.address else None,
        area=user.area.strip() if user.area else None,
        created_at=now,
        updated_at=now,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Send verification email via SMTP (Gmail)
    # The raw token is sent to the user and NEVER stored or logged
    sent = email_service.send_verification_email(
        to_email=new_user.email,
        full_name=new_user.full_name,
        raw_token=raw_token,
        request_base_url=request_base_url,
    )
    if not sent:
        print(f"[FoodShare Email] WARNING: Email delivery failed for {new_user.email}. Check terminal logs for SMTP details.")

    return new_user


def verify_email(
    token_str: str,
    db: d_b.SessionDep,
) -> schemas.VerifyEmailResponse:
    if not token_str or not token_str.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is required",
        )

    # Hash received raw token for database lookup
    token_hash = hash_verification_token(token_str)

    user = db.exec(
        select(User).where(User.verification_token_hash == token_hash)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already-used verification token",
        )

    # If the user is already verified and active
    if user.status == UserStatus.ACTIVE:
        user.verification_token_hash = None
        user.verification_token_expires_at = None
        db.add(user)
        db.commit()
        return schemas.VerifyEmailResponse(
            message="Email is already verified.",
            email_verified=True,
            status=user.status,
        )

    # Check 5-minute token expiration
    now = utc_now()
    if user.verification_token_expires_at:
        token_expires_at = user.verification_token_expires_at
        if token_expires_at.tzinfo is None:
            token_expires_at = token_expires_at.replace(tzinfo=timezone.utc)
        if now > token_expires_at:
            user.verification_token_hash = None
            user.verification_token_expires_at = None
            user.updated_at = now
            db.add(user)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Verification link has expired (valid for {VERIFICATION_TOKEN_EXPIRE_MINUTES} minutes). Please request a new verification email from the app.",
            )

    # Valid token: update status to pending_admin, set email_verified, and invalidate token
    user.email_verified = True
    user.email_verified_at = now
    user.status = UserStatus.PENDING_ADMIN
    user.approval_status = ApprovalStatus.PENDING
    user.verification_token_hash = None  # Invalidate immediately - single use
    user.verification_token_expires_at = None
    user.updated_at = now
    user.updated_at = now

    db.add(user)
    db.commit()
    db.refresh(user)

    return schemas.VerifyEmailResponse(
        message="Email verified successfully. Your account is now pending administrator review.",
        email_verified=True,
        status=UserStatus.PENDING_ADMIN,
    )


def resend_verification(
    request_data: schemas.ResendVerificationRequest,
    db: d_b.SessionDep,
    request_base_url: str | None = None,
) -> schemas.ResendVerificationResponse:
    email_clean = request_data.email.lower().strip()

    user = db.exec(
        select(User).where(User.email == email_clean)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found",
        )

    if user.status == UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified and account is active",
        )

    if user.status == UserStatus.PENDING_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified. Your account is pending administrator review.",
        )

    if user.status == UserStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has been rejected by an administrator.",
        )

    if user.status != UserStatus.PENDING_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is not awaiting email verification.",
        )

    # Rate limiting / cooldown check
    now = utc_now()
    if user.last_verification_sent_at:
        last_sent = user.last_verification_sent_at
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        elapsed_seconds = (now - last_sent).total_seconds()
        if elapsed_seconds < VERIFICATION_RESEND_COOLDOWN_SECONDS:
            remaining = int(VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed_seconds)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} seconds before requesting another verification email.",
            )

    # Generate new secure token and invalidate previous one
    raw_token, token_hash = generate_verification_token()
    user.verification_token_hash = token_hash
    user.verification_token_expires_at = now + timedelta(minutes=VERIFICATION_TOKEN_EXPIRE_MINUTES)
    user.last_verification_sent_at = now
    user.updated_at = now

    db.add(user)
    db.commit()

    sent = email_service.send_verification_email(
        to_email=user.email,
        full_name=user.full_name,
        raw_token=raw_token,
        request_base_url=request_base_url,
    )
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please check your SMTP settings in .env.",
        )

    return schemas.ResendVerificationResponse(
        message="Verification email sent. Please check your inbox.",
    )


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

    # Enforce status == active
    if find_user.status != UserStatus.ACTIVE:
        if find_user.status == UserStatus.PENDING_EMAIL:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your email is not verified yet. Please check your email to verify your account.",
            )
        elif find_user.status == UserStatus.PENDING_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is pending admin approval",
            )
        elif find_user.status == UserStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been rejected by an administrator",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not approved yet",
            )

    access_token = token.create_access_token(
        data={"sub": find_user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

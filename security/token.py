from datetime import datetime, timedelta, timezone

import jwt

from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
)


def create_access_token(
    data: dict,
    expires: timedelta | None = None,
):
    to_encode = data.copy()

    if expires:
        expire = datetime.now(timezone.utc) + expires
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def verify_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_email = payload.get("sub")

        if not user_email:
            raise credentials_exception

        return user_email

    except jwt.InvalidTokenError:
        raise credentials_exception
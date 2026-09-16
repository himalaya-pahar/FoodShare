from fastapi import HTTPException, status

import database as d_b
import schemas
from models import User, utc_now


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned_value = value.strip()
    return cleaned_value or None


def update_my_profile(
    profile_data: schemas.UserProfileUpdate,
    current_user: User,
    db: d_b.SessionDep,
) -> User:
    update_data = profile_data.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        cleaned_value = _clean_optional_string(value)

        if field_name == "full_name" and cleaned_value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Full name cannot be empty",
            )

        setattr(current_user, field_name, cleaned_value)

    if update_data:
        current_user.updated_at = utc_now()
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    return current_user

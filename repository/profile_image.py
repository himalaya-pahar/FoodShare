from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlmodel import select

import database as d_b
import schemas
from models import MediaUploadStatus, User, UserProfileImage
from storage import (
    SUPABASE_PROFILE_IMAGES_BUCKET,
    create_private_read_url,
    create_profile_image_upload_target,
    supabase,
)


CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def profile_image_to_response(
    profile_image: UserProfileImage,
) -> schemas.ShowUserProfileImage:
    return schemas.ShowUserProfileImage(
        id=profile_image.id,
        user_id=profile_image.user_id,
        media_url=create_private_read_url(
            SUPABASE_PROFILE_IMAGES_BUCKET,
            profile_image.storage_key,
        ),
        created_at=profile_image.created_at,
        updated_at=profile_image.updated_at,
    )


def request_profile_image_upload(
    upload_data: schemas.ProfileImageUploadRequest,
    current_user: User,
    db: d_b.SessionDep,
) -> schemas.ProfileImageUploadUrl:
    existing_image = db.exec(
        select(UserProfileImage).where(
            UserProfileImage.user_id == current_user.id
        )
    ).first()

    if existing_image:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delete the existing profile image before uploading a new one",
        )

    extension = CONTENT_TYPE_EXTENSIONS[upload_data.content_type]
    storage_key = f"profiles/{current_user.id}/{uuid4()}.{extension}"

    profile_image = UserProfileImage(
        user_id=current_user.id,
        content_type=upload_data.content_type,
        storage_key=storage_key,
        upload_status=MediaUploadStatus.PENDING,
    )

    db.add(profile_image)
    db.commit()
    db.refresh(profile_image)

    try:
        upload_target = create_profile_image_upload_target(
            profile_image.storage_key
        )
    except Exception:
        db.delete(profile_image)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create profile image upload URL",
        )

    return schemas.ProfileImageUploadUrl(
        image_id=profile_image.id,
        upload_url=upload_target["upload_url"],
    )


def complete_profile_image_upload(
    image_id: int,
    current_user: User,
    db: d_b.SessionDep,
) -> schemas.ShowUserProfileImage:
    profile_image = db.get(UserProfileImage, image_id)

    if not profile_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile image not found",
        )

    if profile_image.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this profile image",
        )

    if profile_image.upload_status != MediaUploadStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This profile image upload is already completed",
        )

    try:
        create_private_read_url(
            SUPABASE_PROFILE_IMAGES_BUCKET,
            profile_image.storage_key,
            expires_in=60,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload the profile image before completing it",
        )

    profile_image.upload_status = MediaUploadStatus.READY
    profile_image.updated_at = datetime.now(timezone.utc)

    db.add(profile_image)
    db.commit()
    db.refresh(profile_image)

    return profile_image_to_response(profile_image)


def get_my_profile_image(
    current_user: User,
    db: d_b.SessionDep,
) -> schemas.ShowUserProfileImage | None:
    profile_image = db.exec(
        select(UserProfileImage).where(
            UserProfileImage.user_id == current_user.id,
            UserProfileImage.upload_status == MediaUploadStatus.READY,
        )
    ).first()

    if not profile_image:
        return None

    return profile_image_to_response(profile_image)


def delete_my_profile_image(
    image_id: int,
    current_user: User,
    db: d_b.SessionDep,
) -> None:
    profile_image = db.get(UserProfileImage, image_id)

    if not profile_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile image not found",
        )

    if profile_image.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this profile image",
        )

    if profile_image.upload_status == MediaUploadStatus.READY:
        try:
            supabase.storage.from_(SUPABASE_PROFILE_IMAGES_BUCKET).remove(
                [profile_image.storage_key]
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not delete profile image from storage",
            )

    db.delete(profile_image)
    db.commit()
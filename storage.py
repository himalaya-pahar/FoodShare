from supabase import Client, create_client

from config import (
    SUPABASE_DONATION_MEDIA_BUCKET,
    SUPABASE_PROFILE_IMAGES_BUCKET,
    SUPABASE_SECRET_KEY,
    SUPABASE_URL,
)

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError("Supabase Storage configuration is missing")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


def create_upload_target(
    bucket: str,
    storage_key: str,
) -> dict[str, str]:
    result = supabase.storage.from_(bucket).create_signed_upload_url(
        storage_key
    )

    return {
        "storage_key": result["path"],
        "upload_url": result["signed_url"],
    }


def create_private_read_url(
    bucket: str,
    storage_key: str,
    expires_in: int = 3600,
) -> str:
    result = supabase.storage.from_(bucket).create_signed_url(
        storage_key,
        expires_in,
    )

    signed_url = result["signedURL"]

    if not signed_url:
        raise RuntimeError("Could not create a signed media URL")

    return signed_url


def create_profile_image_upload_target(
    storage_key: str,
) -> dict[str, str]:
    return create_upload_target(
        SUPABASE_PROFILE_IMAGES_BUCKET,
        storage_key,
    )


def create_donation_media_upload_target(
    storage_key: str,
) -> dict[str, str]:
    return create_upload_target(
        SUPABASE_DONATION_MEDIA_BUCKET,
        storage_key,
    )
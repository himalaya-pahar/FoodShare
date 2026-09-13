from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlmodel import select

import database as d_b
import schemas
from config import SUPABASE_DONATION_MEDIA_BUCKET
from models import (
    Donation,
    DonationMedia,
    DonationStatus,
    MediaType,
    MediaUploadStatus,
    User,
)
from storage import (
    create_donation_media_upload_target,
    create_private_read_url,
    supabase,
)


CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
}

MAX_IMAGES_PER_DONATION = 5
MAX_VIDEOS_PER_DONATION = 1


def get_owned_available_donation(
    donation_id: int,
    restaurant: User,
    db: d_b.SessionDep,
) -> Donation:
    donation = db.get(Donation, donation_id)

    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation not found",
        )

    if donation.restaurant_id != restaurant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this donation",
        )

    if donation.status != DonationStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media can only be changed while donation is available",
        )

    return donation


def donation_media_to_response(
    media: DonationMedia,
) -> schemas.ShowDonationMedia:
    return schemas.ShowDonationMedia(
        id=media.id,
        donation_id=media.donation_id,
        media_type=media.media_type,
        media_url=create_private_read_url(
            SUPABASE_DONATION_MEDIA_BUCKET,
            media.storage_key,
        ),
        sort_order=media.sort_order,
        created_at=media.created_at,
    )


def request_donation_media_upload(
    donation_id: int,
    upload_data: schemas.DonationMediaUploadRequest,
    restaurant: User,
    db: d_b.SessionDep,
) -> schemas.DonationMediaUploadUrl:
    donation = get_owned_available_donation(
        donation_id,
        restaurant,
        db,
    )

    media_type = (
        MediaType.IMAGE
        if upload_data.content_type.startswith("image/")
        else MediaType.VIDEO
    )

    existing_media = db.exec(
        select(DonationMedia).where(
            DonationMedia.donation_id == donation.id
        )
    ).all()

    image_count = sum(
        media.media_type == MediaType.IMAGE
        for media in existing_media
    )

    video_count = sum(
        media.media_type == MediaType.VIDEO
        for media in existing_media
    )

    if (
        media_type == MediaType.IMAGE
        and image_count >= MAX_IMAGES_PER_DONATION
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A donation can have at most 5 images",
        )

    if (
        media_type == MediaType.VIDEO
        and video_count >= MAX_VIDEOS_PER_DONATION
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A donation can have at most 1 video",
        )

    extension = CONTENT_TYPE_EXTENSIONS[upload_data.content_type]
    storage_key = f"donations/{donation.id}/{uuid4()}.{extension}"

    media = DonationMedia(
        donation_id=donation.id,
        content_type=upload_data.content_type,
        media_type=media_type,
        storage_key=storage_key,
        sort_order=upload_data.sort_order,
        upload_status=MediaUploadStatus.PENDING,
    )

    db.add(media)
    db.commit()
    db.refresh(media)

    try:
        upload_target = create_donation_media_upload_target(
            media.storage_key
        )
    except Exception:
        db.delete(media)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create donation media upload URL",
        )

    return schemas.DonationMediaUploadUrl(
        media_id=media.id,
        upload_url=upload_target["upload_url"],
    )


def complete_donation_media_upload(
    media_id: int,
    restaurant: User,
    db: d_b.SessionDep,
) -> schemas.ShowDonationMedia:
    media = db.get(DonationMedia, media_id)

    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation media not found",
        )

    get_owned_available_donation(
        media.donation_id,
        restaurant,
        db,
    )

    if media.upload_status != MediaUploadStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This donation media upload is already completed",
        )

    try:
        create_private_read_url(
            SUPABASE_DONATION_MEDIA_BUCKET,
            media.storage_key,
            expires_in=60,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload the media before completing it",
        )

    media.upload_status = MediaUploadStatus.READY
    media.updated_at = datetime.now(timezone.utc)

    db.add(media)
    db.commit()
    db.refresh(media)

    return donation_media_to_response(media)


def get_donation_media(
    donation_id: int,
    db: d_b.SessionDep,
) -> list[schemas.ShowDonationMedia]:
    donation = db.get(Donation, donation_id)

    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation not found",
        )

    media_items = db.exec(
        select(DonationMedia)
        .where(
            DonationMedia.donation_id == donation_id,
            DonationMedia.upload_status == MediaUploadStatus.READY,
        )
        .order_by(
            DonationMedia.sort_order,
            DonationMedia.created_at,
        )
    ).all()

    return [
        donation_media_to_response(media)
        for media in media_items
    ]


def delete_donation_media(
    media_id: int,
    restaurant: User,
    db: d_b.SessionDep,
) -> None:
    media = db.get(DonationMedia, media_id)

    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donation media not found",
        )

    get_owned_available_donation(
        media.donation_id,
        restaurant,
        db,
    )

    try:
        supabase.storage.from_(
            SUPABASE_DONATION_MEDIA_BUCKET
        ).remove([media.storage_key])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not delete donation media from storage",
        )

    db.delete(media)
    db.commit()
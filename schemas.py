from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from models import ApprovalStatus, UserRole, DonationStatus, PickupRequestStatus, AuditEntityType, MediaType
from datetime import datetime
from typing import Literal


class UserSignup(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    organization_name: Optional[str] = Field(default=None, max_length=150)

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    role: UserRole

    phone: Optional[str] = Field(default=None, max_length=30)
    address: Optional[str] = None
    area: Optional[str] = Field(default=None, max_length=100)


class ShowUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    organization_name: Optional[str] = None
    email: str
    role: UserRole
    approval_status: ApprovalStatus
    phone: Optional[str] = None
    address: Optional[str] = None
    area: Optional[str] = None


class ApprovalUpdate(BaseModel):
    approval_status: ApprovalStatus



class DonationCreate(BaseModel):
    food_name: str = Field(min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)

    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)

    prepared_at: datetime
    pickup_deadline: datetime

    pickup_area: str = Field(min_length=2, max_length=100)
    pickup_address: str = Field(min_length=5, max_length=255)

    storage_notes: Optional[str] = Field(default=None, max_length=500)
    allergen_info: Optional[str] = Field(default=None, max_length=500)


class DonationUpdate(BaseModel):
    food_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)

    quantity: Optional[float] = Field(default=None, gt=0)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=30)

    prepared_at: Optional[datetime] = None
    pickup_deadline: Optional[datetime] = None

    pickup_area: Optional[str] = Field(default=None, min_length=2, max_length=100)
    pickup_address: Optional[str] = Field(default=None, min_length=5, max_length=255)

    storage_notes: Optional[str] = Field(default=None, max_length=500)
    allergen_info: Optional[str] = Field(default=None, max_length=500)


class ShowDonation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int

    food_name: str
    description: Optional[str] = None
    quantity: float
    unit: str

    prepared_at: datetime
    pickup_deadline: datetime

    pickup_area: str
    pickup_address: str
    storage_notes: Optional[str] = None
    allergen_info: Optional[str] = None

    status: DonationStatus
    created_at: datetime
    updated_at: datetime



class PickupRequestCreate(BaseModel):
    estimated_pickup_at: datetime
    message: Optional[str] = Field(default=None, max_length=500)


class ShowPickupRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    donation_id: int
    ngo_id: int

    estimated_pickup_at: datetime
    message: Optional[str] = None
    status: PickupRequestStatus

    requested_at: datetime
    updated_at: datetime


class ShowStatusHistory(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    donation_id: int
    pickup_request_id: Optional[int] = None
    actor_id: int

    entity_type: AuditEntityType
    action: str

    old_status: Optional[str] = None
    new_status: Optional[str] = None
    note: Optional[str] = None

    created_at: datetime


class ShowUserProfileImage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    media_url: str
    created_at: datetime
    updated_at: datetime


class ShowDonationMedia(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    donation_id: int
    media_type: MediaType
    media_url: str
    sort_order: int
    created_at: datetime

class ProfileImageUploadRequest(BaseModel):
    content_type: Literal[
        "image/jpeg",
        "image/png",
        "image/webp",
    ]


class ProfileImageUploadUrl(BaseModel):
    image_id: int
    upload_url: str
    expires_in: int = 7200

class DonationMediaUploadRequest(BaseModel):
    content_type: Literal[
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
    ]

    sort_order: int = Field(default=0, ge=0)


class DonationMediaUploadUrl(BaseModel):
    media_id: int
    upload_url: str
    expires_in: int = 7200
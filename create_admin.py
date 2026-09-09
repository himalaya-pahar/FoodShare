from sqlmodel import Session, select

import database as d_b
from models import ApprovalStatus, User, UserRole
from security import hashing


d_b.create_db_and_tables()

admin_email = "admin@foodshare.com"
admin_password = "Admin@12345"

with Session(d_b.engine) as db:
    existing_admin = db.exec(
        select(User).where(User.email == admin_email)
    ).first()

    if existing_admin:
        print("Admin already exists")
    else:
        admin = User(
            full_name="FoodShare Administrator",
            organization_name="FoodShare",
            email=admin_email,
            password_hash=hashing.get_hash_password(admin_password),
            role=UserRole.ADMIN,
            approval_status=ApprovalStatus.APPROVED,
        )

        db.add(admin)
        db.commit()

        print("Admin created successfully")
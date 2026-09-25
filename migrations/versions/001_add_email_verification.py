"""Add email verification and user status lifecycle fields

Revision ID: 001_add_email_verification
Revises: 
Create Date: 2026-09-25 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '001_add_email_verification'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to users table
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_email"))
        batch_op.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0" if is_sqlite else "false")))
        batch_op.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("verification_token_hash", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("last_verification_sent_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("verification_token_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_users_status", ["status"], unique=False)
        batch_op.create_index("ix_users_verification_token_hash", ["verification_token_hash"], unique=False)

    # 2. Backfill existing users
    if is_sqlite:
        op.execute("""
            UPDATE users
            SET status = 'active', email_verified = 1, email_verified_at = created_at
            WHERE approval_status = 'APPROVED'
        """)
        op.execute("""
            UPDATE users
            SET status = 'rejected', email_verified = 1
            WHERE approval_status = 'REJECTED'
        """)
        op.execute("""
            UPDATE users
            SET status = 'pending_admin', email_verified = 1
            WHERE approval_status = 'PENDING'
        """)
    else:
        op.execute("""
            UPDATE users
            SET status = 'active', email_verified = TRUE, email_verified_at = created_at
            WHERE approval_status = 'APPROVED'
        """)
        op.execute("""
            UPDATE users
            SET status = 'rejected', email_verified = TRUE
            WHERE approval_status = 'REJECTED'
        """)
        op.execute("""
            UPDATE users
            SET status = 'pending_admin', email_verified = TRUE
            WHERE approval_status = 'PENDING'
        """)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_verification_token_hash")
        batch_op.drop_index("ix_users_status")
        batch_op.drop_column("verification_token_expires_at")
        batch_op.drop_column("last_verification_sent_at")
        batch_op.drop_column("verification_token_hash")
        batch_op.drop_column("email_verified_at")
        batch_op.drop_column("email_verified")
        batch_op.drop_column("status")

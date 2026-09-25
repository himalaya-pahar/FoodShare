"""
Database migration script for FoodShare.
Adds email verification and user status lifecycle fields to the users table.
Supports both PostgreSQL (production/Supabase) and SQLite (local dev).
"""
import sys
from sqlalchemy import inspect, text
import database as d_b

def run_migrations():
    engine = d_b.engine
    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    print(f"Current columns in 'users': {sorted(existing_columns)}")

    is_sqlite = engine.dialect.name == "sqlite"

    with engine.begin() as conn:
        # Add 'status'
        if "status" not in existing_columns:
            print("Adding 'status' column...")
            if is_sqlite:
                conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(30) DEFAULT 'pending_email' NOT NULL"))
            else:
                conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(30) DEFAULT 'pending_email' NOT NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_status ON users(status)"))

        # Add 'email_verified'
        if "email_verified" not in existing_columns:
            print("Adding 'email_verified' column...")
            if is_sqlite:
                conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0 NOT NULL"))
            else:
                conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE NOT NULL"))

        # Add 'email_verified_at'
        if "email_verified_at" not in existing_columns:
            print("Adding 'email_verified_at' column...")
            if is_sqlite:
                conn.execute(text("ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMP NULL"))
            else:
                conn.execute(text("ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMPTZ NULL"))

        # Add 'verification_token_hash'
        if "verification_token_hash" not in existing_columns:
            print("Adding 'verification_token_hash' column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN verification_token_hash VARCHAR(255) NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_verification_token_hash ON users(verification_token_hash)"))

        # Add 'last_verification_sent_at'
        if "last_verification_sent_at" not in existing_columns:
            print("Adding 'last_verification_sent_at' column...")
            if is_sqlite:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_verification_sent_at TIMESTAMP NULL"))
            else:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_verification_sent_at TIMESTAMPTZ NULL"))

        # Add 'verification_token_expires_at'
        if "verification_token_expires_at" not in existing_columns:
            print("Adding 'verification_token_expires_at' column...")
            if is_sqlite:
                conn.execute(text("ALTER TABLE users ADD COLUMN verification_token_expires_at TIMESTAMP NULL"))
            else:
                conn.execute(text("ALTER TABLE users ADD COLUMN verification_token_expires_at TIMESTAMPTZ NULL"))

        # Backfill existing users based on approval_status
        print("Backfilling existing users...")
        if is_sqlite:
            conn.execute(text("""
                UPDATE users
                SET status = 'active', email_verified = 1, email_verified_at = created_at
                WHERE approval_status = 'APPROVED' AND (status IS NULL OR status = 'pending_email')
            """))
            conn.execute(text("""
                UPDATE users
                SET status = 'rejected', email_verified = 1
                WHERE approval_status = 'REJECTED' AND (status IS NULL OR status = 'pending_email')
            """))
            conn.execute(text("""
                UPDATE users
                SET status = 'pending_admin', email_verified = 1
                WHERE approval_status = 'PENDING' AND (status IS NULL OR status = 'pending_email')
            """))
        else:
            conn.execute(text("""
                UPDATE users
                SET status = 'active', email_verified = TRUE, email_verified_at = created_at
                WHERE approval_status = 'APPROVED' AND (status IS NULL OR status = 'pending_email')
            """))
            conn.execute(text("""
                UPDATE users
                SET status = 'rejected', email_verified = TRUE
                WHERE approval_status = 'REJECTED' AND (status IS NULL OR status = 'pending_email')
            """))
            conn.execute(text("""
                UPDATE users
                SET status = 'pending_admin', email_verified = TRUE
                WHERE approval_status = 'PENDING' AND (status IS NULL OR status = 'pending_email')
            """))

    print("Migration completed successfully!")

if __name__ == "__main__":
    run_migrations()

-- ==============================================================================
-- Migration: Add Email Verification and Account Status Lifecycle to users table
-- Target: PostgreSQL / Supabase
-- ==============================================================================

-- 1. Add columns if they do not exist
ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'pending_email' NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_hash VARCHAR(255) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_verification_sent_at TIMESTAMPTZ NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_expires_at TIMESTAMPTZ NULL;

-- 2. Create indices for fast lookup
CREATE INDEX IF NOT EXISTS ix_users_status ON users(status);
CREATE INDEX IF NOT EXISTS ix_users_verification_token_hash ON users(verification_token_hash);

-- 3. Backfill existing user accounts
UPDATE users
SET status = 'active', email_verified = TRUE, email_verified_at = created_at
WHERE approval_status = 'APPROVED' AND (status IS NULL OR status = 'pending_email');

UPDATE users
SET status = 'rejected', email_verified = TRUE
WHERE approval_status = 'REJECTED' AND (status IS NULL OR status = 'pending_email');

UPDATE users
SET status = 'pending_admin', email_verified = TRUE
WHERE approval_status = 'PENDING' AND (status IS NULL OR status = 'pending_email');

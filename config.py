import os

from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing in .env")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing in .env")

if not ALGORITHM:
    raise RuntimeError("ALGORITHM is missing in .env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

SUPABASE_PROFILE_IMAGES_BUCKET = os.getenv(
    "SUPABASE_PROFILE_IMAGES_BUCKET",
    "profile-images",
)

SUPABASE_DONATION_MEDIA_BUCKET = os.getenv(
    "SUPABASE_DONATION_MEDIA_BUCKET",
    "donation-media",
)

CREATE_TABLES_ON_STARTUP = (
    os.getenv("CREATE_TABLES_ON_STARTUP", "false").lower()
    == "true"
)

UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
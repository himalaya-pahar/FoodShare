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


# ---------------------------------------------------------------------------
# AI Assistant configuration
# ---------------------------------------------------------------------------

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
LLM_API_KEY = os.getenv("LLM_API_KEY")           # generic, used by provider
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")     # alias for convenience

# Embeddings (Gemini text-embedding-004 by default; local sentence-transformers optional)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()
EMBEDDINGS_MODEL = os.getenv(
    "EMBEDDINGS_MODEL",
    "gemini-embedding-001"
    if EMBEDDING_PROVIDER == "gemini"
    else "sentence-transformers/all-MiniLM-L6-v2",
)
# Where sentence-transformers caches model files (if using local provider).
SENTENCE_TRANSFORMERS_HOME = os.getenv("SENTENCE_TRANSFORMERS_HOME", "")
DEFAULT_EMBEDDING_DIM = 768 if EMBEDDING_PROVIDER == "gemini" else 384
EMBEDDING_DIM = int(os.getenv("AI_EMBEDDING_DIM", str(DEFAULT_EMBEDDING_DIM)))

# Vector search
TOP_K = int(os.getenv("AI_TOP_K", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("AI_SIMILARITY_THRESHOLD", "0.40"))

# pgvector ivfflat index: below this row count we skip index creation.
# Sequential scan is faster for small tables, AND an ivfflat index built with
# lists >> sqrt(rows) silently returns empty results for <=> queries.
IVFFLAT_MIN_ROWS = int(os.getenv("AI_IVFFLAT_MIN_ROWS", "1000"))

# Chunking
CHUNK_SIZE = int(os.getenv("AI_CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("AI_CHUNK_OVERLAP", "120"))

# Conversation memory
SESSION_TTL_MINUTES = int(os.getenv("AI_SESSION_TTL_MINUTES", "60"))
SESSION_MAX_TURNS = int(os.getenv("AI_SESSION_MAX_TURNS", "6"))

# Logging
AI_DEBUG_LOG_CONTENT = (
    os.getenv("AI_DEBUG_LOG_CONTENT", "false").lower() == "true"
)

# Comma-separated origins allowed to call the separately deployed AI service
# from a browser. Native React Native requests do not rely on browser CORS.
AI_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("AI_CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

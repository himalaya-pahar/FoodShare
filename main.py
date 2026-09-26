from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import database as d_b
import models
from ai.api.routes import router as ai_router
from routers import (
    admin,
    authenticate,
    donation,
    donation_media,
    history,
    pickup,
    profile_image,
    status_history,
    user,
)
from config import CREATE_TABLES_ON_STARTUP


@asynccontextmanager
async def lifespan(app:FastAPI):
    print("server starting...")
    if CREATE_TABLES_ON_STARTUP:
        d_b.create_db_and_tables()
    yield
    print("server shutting down...")

app = FastAPI(
    title="FoodShare API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      
    allow_credentials=True,
    allow_methods=["*"],        
    allow_headers=["*"],        
)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)

app.include_router(authenticate.router)
app.include_router(admin.router)
app.include_router(donation.router)
app.include_router(pickup.router)
app.include_router(status_history.router)
app.include_router(profile_image.router)
app.include_router(donation_media.router)
app.include_router(user.router)
app.include_router(history.router)
app.include_router(ai_router)


@app.get("/health", tags=["Health"], include_in_schema=False)
def health() -> dict[str, str]:
    """Basic liveness check."""
    return {"status": "ok"}


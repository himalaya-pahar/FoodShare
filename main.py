from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import database as d_b
import models
from routers import admin, authenticate, donation, pickup, status_history


@asynccontextmanager
async def lifespan(app:FastAPI):
    print("server starting...")
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

app.include_router(authenticate.router)
app.include_router(admin.router)
app.include_router(donation.router)
app.include_router(pickup.router)
app.include_router(status_history.router)
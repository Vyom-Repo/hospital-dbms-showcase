"""
Application Entry Point
FastAPI application routing and lifecycle configuration.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import close_pool, init_pool
from routes.admin import router as admin_router
from routes.appointments import router as appointments_router
from routes.billing import router as billing_router
from routes.departments import router as departments_router
from routes.doctors import router as doctors_router
from routes.medical_records import router as medical_records_router
from routes.patients import router as patients_router
from routes.rooms import router as rooms_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Hospital DBMS Showcase",
    description="High-Performance PostgreSQL Enterprise Management System with Raw SQL & FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(departments_router)
app.include_router(patients_router)
app.include_router(doctors_router)
app.include_router(appointments_router)
app.include_router(rooms_router)
app.include_router(medical_records_router)
app.include_router(billing_router)
app.include_router(admin_router)

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


app.mount("/", StaticFiles(directory=static_dir), name="static")

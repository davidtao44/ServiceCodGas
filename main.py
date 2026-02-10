from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database.database import engine
from app.models.models import Base
from app.auth.auth import router as auth_router
from app.inventory.inventory import router as inventory_router
from app.dashboard.dashboard import router as dashboard_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Gas Inventory Management System",
    description="API for managing gas tank inventory with role-based access control",
    version="1.0.0"
)

# Configurar CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(inventory_router, prefix="/inventory", tags=["inventory"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])

@app.get("/")
def read_root():
    return {"message": "Gas Inventory Management API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

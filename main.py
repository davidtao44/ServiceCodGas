from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database.database import engine
from app.models.models import Base
from app.auth.auth import router as auth_router
from app.users.users import router as users_router
from app.tank_types.tank_types import router as tank_types_router
from app.inventory.inventory import router as inventory_router
from app.embasado.embasado import router as embasado_router
from app.ventas.ventas import router as ventas_router
from app.jornadas.jornadas import router as jornadas_router
from app.debts.debts import router as debts_router
from app.dashboard.dashboard import router as dashboard_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Codgas - Sistema de Gestión de Cilindros de Gas",
    description="API para gestionar inventario, envasado, ventas y jornadas",
    version="1.0.0"
)

origins = [
    "http://173.212.221.21:5000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(users_router, prefix="/api", tags=["usuarios"])
app.include_router(tank_types_router, prefix="/api", tags=["tipos-cilindros"])
app.include_router(inventory_router, prefix="/api", tags=["inventario"])
app.include_router(embasado_router, prefix="/api", tags=["embasado"])
app.include_router(ventas_router, prefix="/api", tags=["ventas"])
app.include_router(jornadas_router, prefix="/api", tags=["jornadas"])
app.include_router(debts_router, prefix="/api", tags=["deudas"])
app.include_router(dashboard_router, prefix="/api", tags=["dashboard"])

@app.get("/")
def read_root():
    return {"message": "Codgas API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

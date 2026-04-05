from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database.database import get_db
from app.models.models import GasLoad, User
from app.schemas.schemas import GasLoad as GasLoadSchema, GasLoadCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.post("/gas-loads", response_model=GasLoadSchema)
def create_gas_load(
    gas_load: GasLoadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if gas_load.kg_loaded <= 0:
        raise HTTPException(status_code=400, detail="La cantidad de gas debe ser mayor a 0")
    
    db_gas_load = GasLoad(
        kg_loaded=gas_load.kg_loaded,
        vehicle_plate=gas_load.vehicle_plate,
        received_by_user_id=gas_load.received_by_user_id,
        notes=gas_load.notes
    )
    
    db.add(db_gas_load)
    db.commit()
    db.refresh(db_gas_load)
    
    print(f"[GAS_LOADS] Usuario {current_user.email} registró carga de {gas_load.kg_loaded:.2f} kg de gas, vehículo: {gas_load.vehicle_plate or 'N/A'}")
    
    return db_gas_load

@router.get("/gas-loads", response_model=List[GasLoadSchema])
def get_gas_loads(
    received_by_user_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(GasLoad)
    
    if received_by_user_id:
        query = query.filter(GasLoad.received_by_user_id == received_by_user_id)
    
    return query.order_by(GasLoad.date.desc()).all()

@router.get("/gas-loads/summary")
def get_gas_loads_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    total = db.query(func.coalesce(func.sum(GasLoad.kg_loaded), 0)).scalar()
    
    return {"total_kg_loaded": float(total)}

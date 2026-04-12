from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from app.core.database.database import get_db
from app.models.models import GasLoad, User, Vehicle
from app.schemas.schemas import GasLoad as GasLoadSchema, GasLoadCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

def paginate_query(query, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    total = query.count()
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    items = query.offset(offset).limit(limit).all()
    return items, total, total_pages

@router.post("/gas-loads", response_model=GasLoadSchema)
def create_gas_load(
    gas_load: GasLoadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if gas_load.kg_loaded <= 0:
        raise HTTPException(status_code=400, detail="La cantidad de gas debe ser mayor a 0")
    
    vehicle_id = gas_load.vehicle_id
    
    if gas_load.new_vehicle:
        existing_vehicle = db.query(Vehicle).filter(Vehicle.plate == gas_load.new_vehicle.plate).first()
        if existing_vehicle:
            vehicle_id = existing_vehicle.id
        else:
            new_vehicle = Vehicle(**gas_load.new_vehicle.model_dump())
            db.add(new_vehicle)
            db.flush()
            vehicle_id = new_vehicle.id
    
    db_gas_load = GasLoad(
        kg_loaded=gas_load.kg_loaded,
        vehicle_plate=gas_load.vehicle_plate,
        vehicle_id=vehicle_id,
        received_by_user_id=gas_load.received_by_user_id,
        notes=gas_load.notes
    )
    
    db.add(db_gas_load)
    db.commit()
    db.refresh(db_gas_load)
    
    vehicle_info = ""
    if vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if vehicle:
            vehicle_info = f", vehículo: {vehicle.name} ({vehicle.plate})"
    
    print(f"[GAS_LOADS] Usuario {current_user.email} registró carga de {gas_load.kg_loaded:.2f} kg de gas{vehicle_info}")
    
    return db_gas_load

@router.get("/gas-loads")
def get_gas_loads(
    received_by_user_id: int = None,
    vehicle_id: int = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(GasLoad).options(joinedload(GasLoad.vehicle))
    
    if received_by_user_id:
        query = query.filter(GasLoad.received_by_user_id == received_by_user_id)
    
    if vehicle_id:
        query = query.filter(GasLoad.vehicle_id == vehicle_id)
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(GasLoad.date >= start)
        except:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(GasLoad.date <= end)
        except:
            pass
    
    query = query.order_by(GasLoad.date.desc())
    
    items, total, total_pages = paginate_query(query, page, limit)
    
    return {
        "data": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

@router.get("/gas-loads/summary")
def get_gas_loads_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    total = db.query(func.coalesce(func.sum(GasLoad.kg_loaded), 0)).scalar()
    
    return {"total_kg_loaded": float(total)}

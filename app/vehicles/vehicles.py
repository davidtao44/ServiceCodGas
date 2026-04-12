from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database.database import get_db
from app.models.models import Vehicle, User
from app.schemas.schemas import Vehicle as VehicleSchema, VehicleCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.get("/vehicles", response_model=List[VehicleSchema])
def get_vehicles(
    location: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Vehicle)
    if is_active is not None:
        query = query.filter(Vehicle.is_active == is_active)
    if location:
        query = query.filter(Vehicle.location == location)
    return query.order_by(Vehicle.name).all()

@router.post("/vehicles", response_model=VehicleSchema)
def create_vehicle(
    vehicle: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    existing = db.query(Vehicle).filter(Vehicle.plate == vehicle.plate).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un vehículo con esa placa")
    
    db_vehicle = Vehicle(**vehicle.model_dump())
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle

@router.put("/vehicles/{vehicle_id}", response_model=VehicleSchema)
def update_vehicle(
    vehicle_id: int,
    vehicle: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not db_vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    
    for key, value in vehicle.model_dump().items():
        setattr(db_vehicle, key, value)
    
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle

@router.delete("/vehicles/{vehicle_id}")
def deactivate_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not db_vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    
    db_vehicle.is_active = False
    db.commit()
    return {"message": "Vehículo desactivado"}
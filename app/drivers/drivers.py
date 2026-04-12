from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database.database import get_db
from app.models.models import Driver, User
from app.schemas.schemas import Driver as DriverSchema, DriverCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.get("/drivers", response_model=List[DriverSchema])
def get_drivers(
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Driver)
    if is_active is not None:
        query = query.filter(Driver.is_active == is_active)
    return query.order_by(Driver.name).all()

@router.post("/drivers", response_model=DriverSchema)
def create_driver(
    driver: DriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_driver = Driver(**driver.model_dump())
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)
    return db_driver

@router.put("/drivers/{driver_id}", response_model=DriverSchema)
def update_driver(
    driver_id: int,
    driver: DriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not db_driver:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    
    for key, value in driver.model_dump().items():
        setattr(db_driver, key, value)
    
    db.commit()
    db.refresh(db_driver)
    return db_driver

@router.delete("/drivers/{driver_id}")
def deactivate_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not db_driver:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    
    db_driver.is_active = False
    db.commit()
    return {"message": "Conductor desactivado"}
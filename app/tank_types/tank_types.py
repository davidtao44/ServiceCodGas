from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database.database import get_db
from app.models.models import TankType, UserRole
from app.schemas.schemas import TankType as TankTypeSchema, TankTypeCreate, TankTypeUpdate
from app.auth.auth import get_current_active_user

router = APIRouter()

def require_role(allowed_roles: List[str]):
    def role_checker(current_user = Depends(get_current_active_user)):
        if current_user.role.value not in allowed_roles:
            raise HTTPException(status_code=403, detail="No tienes permisos para esta acción")
        return current_user
    return role_checker

@router.get("/tank-types", response_model=List[TankTypeSchema])
def get_tank_types(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    return db.query(TankType).filter(TankType.is_active == True).offset(skip).limit(limit).all()

@router.post("/tank-types", response_model=TankTypeSchema)
def create_tank_type(
    tank_type: TankTypeCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["superadmin"]))
):
    db_tank_type = TankType(**tank_type.model_dump())
    db.add(db_tank_type)
    db.commit()
    db.refresh(db_tank_type)
    return db_tank_type

@router.get("/tank-types/{tank_type_id}", response_model=TankTypeSchema)
def get_tank_type(
    tank_type_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    tank_type = db.query(TankType).filter(TankType.id == tank_type_id).first()
    if not tank_type:
        raise HTTPException(status_code=404, detail="Tipo de cilindro no encontrado")
    return tank_type

@router.put("/tank-types/{tank_type_id}", response_model=TankTypeSchema)
def update_tank_type(
    tank_type_id: int,
    tank_type_update: TankTypeUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["superadmin"]))
):
    tank_type = db.query(TankType).filter(TankType.id == tank_type_id).first()
    if not tank_type:
        raise HTTPException(status_code=404, detail="Tipo de cilindro no encontrado")
    
    update_data = tank_type_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tank_type, field, value)
    
    db.commit()
    db.refresh(tank_type)
    return tank_type

@router.delete("/tank-types/{tank_type_id}")
def delete_tank_type(
    tank_type_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["superadmin"]))
):
    tank_type = db.query(TankType).filter(TankType.id == tank_type_id).first()
    if not tank_type:
        raise HTTPException(status_code=404, detail="Tipo de cilindro no encontrado")
    
    tank_type.is_active = False
    db.commit()
    return {"message": "Tipo de cilindro eliminado correctamente"}

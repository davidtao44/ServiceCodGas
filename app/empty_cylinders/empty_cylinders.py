from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database.database import get_db
from app.models.models import EmptyCylinderMovement, TankType, User
from app.schemas.schemas import EmptyCylinderMovement as EmptyCylinderMovementSchema, EmptyCylinderMovementCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.post("/empty-cylinders", response_model=EmptyCylinderMovementSchema)
def create_empty_cylinder_movement(
    movement: EmptyCylinderMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    tank_type = db.query(TankType).filter(TankType.id == movement.cylinder_type_id).first()
    if not tank_type:
        raise HTTPException(status_code=404, detail="Tipo de cilindro no encontrado")
    
    db_movement = EmptyCylinderMovement(
        cylinder_type_id=movement.cylinder_type_id,
        quantity=movement.quantity,
        source=movement.source,
        received_by_user_id=movement.received_by_user_id,
        delivered_by_user_id=movement.delivered_by_user_id,
        notes=movement.notes
    )
    
    db.add(db_movement)
    db.commit()
    db.refresh(db_movement)
    
    print(f"[EMPTY_CYLINDERS] Usuario {current_user.email} registró entrada de {movement.quantity} cilindros vacíos tipo {tank_type.name}")
    
    return db_movement

@router.get("/empty-cylinders", response_model=List[EmptyCylinderMovementSchema])
def get_empty_cylinder_movements(
    cylinder_type_id: int = None,
    source: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(EmptyCylinderMovement)
    
    if cylinder_type_id:
        query = query.filter(EmptyCylinderMovement.cylinder_type_id == cylinder_type_id)
    if source:
        query = query.filter(EmptyCylinderMovement.source == source)
    
    return query.order_by(EmptyCylinderMovement.date.desc()).all()

@router.get("/empty-cylinders/summary")
def get_empty_cylinders_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    results = db.query(
        EmptyCylinderMovement.cylinder_type_id,
        TankType.name,
        func.coalesce(func.sum(EmptyCylinderMovement.quantity), 0).label("total")
    ).join(TankType).group_by(
        EmptyCylinderMovement.cylinder_type_id, TankType.name
    ).all()
    
    return [{"cylinder_type_id": r.cylinder_type_id, "name": r.name, "total": r.total} for r in results]

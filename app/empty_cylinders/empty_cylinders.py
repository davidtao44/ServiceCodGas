from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database.database import get_db
from app.models.models import EmptyCylinderMovement, EmptyCylinderMovementDetail, TankType, User
from app.schemas.schemas import EmptyCylinderMovement as EmptyCylinderMovementSchema, EmptyCylinderMovementCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.post("/empty-cylinders", response_model=EmptyCylinderMovementSchema)
def create_empty_cylinder_movement(
    movement: EmptyCylinderMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not movement.details:
        raise HTTPException(status_code=400, detail="Debe incluir al menos un detalle")
    
    for detail in movement.details:
        tank_type = db.query(TankType).filter(TankType.id == detail.cylinder_type_id).first()
        if not tank_type:
            raise HTTPException(status_code=404, detail=f"Tipo de cilindro {detail.cylinder_type_id} no encontrado")
    
    db_movement = EmptyCylinderMovement(
        source=movement.source,
        received_by_user_id=movement.received_by_user_id,
        delivered_by_user_id=movement.delivered_by_user_id,
        notes=movement.notes
    )
    
    db.add(db_movement)
    db.flush()
    
    for detail in movement.details:
        db_detail = EmptyCylinderMovementDetail(
            movement_id=db_movement.id,
            cylinder_type_id=detail.cylinder_type_id,
            quantity=detail.quantity
        )
        db.add(db_detail)
    
    db.commit()
    db.refresh(db_movement)
    
    total_qty = sum(d.quantity for d in movement.details)
    types_str = ", ".join([f"{d.quantity}x tipo {d.cylinder_type_id}" for d in movement.details])
    print(f"[EMPTY_CYLINDERS] Usuario {current_user.email} registró entrada de {total_qty} cilindros vacíos: {types_str}")
    
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
        query = query.join(EmptyCylinderMovement.details).filter(
            EmptyCylinderMovementDetail.cylinder_type_id == cylinder_type_id
        )
    if source:
        query = query.filter(EmptyCylinderMovement.source == source)
    
    results = query.order_by(EmptyCylinderMovement.date.desc()).all()
    print(f"[EMPTY_CYLINDERS DEBUG] GET /empty-cylinders - Total movimientos: {len(results)}")
    for m in results[:3]:
        print(f"[EMPTY_CYLINDERS DEBUG]   - ID={m.id}, fuente={m.source}, detalles={len(m.details)}")
    
    return results

@router.get("/empty-cylinders/summary")
def get_empty_cylinders_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    results = db.query(
        EmptyCylinderMovementDetail.cylinder_type_id,
        TankType.name,
        func.coalesce(func.sum(EmptyCylinderMovementDetail.quantity), 0).label("total")
    ).join(
        TankType, EmptyCylinderMovementDetail.cylinder_type_id == TankType.id
    ).group_by(
        EmptyCylinderMovementDetail.cylinder_type_id, TankType.name
    ).all()
    
    return [{"cylinder_type_id": r.cylinder_type_id, "name": r.name, "total": r.total} for r in results]

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database.database import get_db
from app.models.models import FillingOperation, TankType, User, EmptyCylinderMovement, GasLoad
from app.schemas.schemas import FillingOperation as FillingOperationSchema, FillingOperationCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.post("/filling", response_model=FillingOperationSchema)
def create_filling_operation(
    operation: FillingOperationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    tank_type = db.query(TankType).filter(TankType.id == operation.cylinder_type_id).first()
    if not tank_type:
        raise HTTPException(status_code=404, detail="Tipo de cilindro no encontrado")
    
    empty_received = db.query(func.coalesce(func.sum(EmptyCylinderMovement.quantity), 0)).filter(
        EmptyCylinderMovement.cylinder_type_id == operation.cylinder_type_id
    ).scalar()
    
    empty_filled = db.query(func.coalesce(func.sum(FillingOperation.quantity), 0)).filter(
        FillingOperation.cylinder_type_id == operation.cylinder_type_id
    ).scalar()
    
    available_empty = empty_received - empty_filled
    
    if operation.quantity > available_empty:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficientes cilindros vacíos. Disponibles: {available_empty}, Solicitados: {operation.quantity}"
        )
    
    gas_total = db.query(func.coalesce(func.sum(GasLoad.kg_loaded), 0)).scalar()
    gas_used = db.query(func.coalesce(func.sum(FillingOperation.kg_used), 0)).scalar()
    available_gas = gas_total - gas_used
    
    kg_needed = operation.quantity * tank_type.capacity
    
    if kg_needed > available_gas:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficiente gas. Disponible: {available_gas:.2f} kg, Necesario: {kg_needed:.2f} kg"
        )
    
    db_operation = FillingOperation(
        cylinder_type_id=operation.cylinder_type_id,
        quantity=operation.quantity,
        kg_used=kg_needed,
        performed_by_user_id=operation.performed_by_user_id,
        notes=operation.notes
    )
    
    db.add(db_operation)
    db.commit()
    db.refresh(db_operation)
    
    print(f"[FILLING] Usuario {current_user.email} embasó {operation.quantity} cilindros tipo {tank_type.name}, {kg_needed:.2f} kg gas usado")
    
    return db_operation

@router.get("/filling", response_model=List[FillingOperationSchema])
def get_filling_operations(
    cylinder_type_id: int = None,
    performed_by_user_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(FillingOperation)
    
    if cylinder_type_id:
        query = query.filter(FillingOperation.cylinder_type_id == cylinder_type_id)
    if performed_by_user_id:
        query = query.filter(FillingOperation.performed_by_user_id == performed_by_user_id)
    
    return query.order_by(FillingOperation.date.desc()).all()

@router.get("/filling/summary")
def get_filling_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    results = db.query(
        FillingOperation.cylinder_type_id,
        TankType.name,
        func.coalesce(func.sum(FillingOperation.quantity), 0).label("total_cylinders"),
        func.coalesce(func.sum(FillingOperation.kg_used), 0).label("total_kg")
    ).join(TankType).group_by(
        FillingOperation.cylinder_type_id, TankType.name
    ).all()
    
    return [{
        "cylinder_type_id": r.cylinder_type_id,
        "name": r.name,
        "total_cylinders": r.total_cylinders,
        "total_kg": float(r.total_kg)
    } for r in results]

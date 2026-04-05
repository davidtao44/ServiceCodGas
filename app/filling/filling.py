from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database.database import get_db
from app.models.models import FillingOperation, FillingOperationDetail, TankType, User, EmptyCylinderMovement, EmptyCylinderMovementDetail, GasLoad
from app.schemas.schemas import FillingOperation as FillingOperationSchema, FillingOperationCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.post("/filling", response_model=FillingOperationSchema)
def create_filling_operation(
    operation: FillingOperationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not operation.details:
        raise HTTPException(status_code=400, detail="Debe incluir al menos un detalle")
    
    for detail in operation.details:
        tank_type = db.query(TankType).filter(TankType.id == detail.cylinder_type_id).first()
        if not tank_type:
            raise HTTPException(status_code=404, detail=f"Tipo de cilindro {detail.cylinder_type_id} no encontrado")
        
        empty_received = db.query(func.coalesce(func.sum(EmptyCylinderMovementDetail.quantity), 0)).join(
            EmptyCylinderMovement
        ).filter(
            EmptyCylinderMovementDetail.cylinder_type_id == detail.cylinder_type_id
        ).scalar()
        
        empty_filled = db.query(func.coalesce(func.sum(FillingOperationDetail.quantity), 0)).join(
            FillingOperation
        ).filter(
            FillingOperationDetail.cylinder_type_id == detail.cylinder_type_id
        ).scalar()
        
        available_empty = empty_received - empty_filled
        
        if detail.quantity > available_empty:
            raise HTTPException(
                status_code=400,
                detail=f"No hay suficientescilindros vacíos para tipo {tank_type.name}. Disponibles: {available_empty}, Solicitados: {detail.quantity}"
            )
    
    gas_total = db.query(func.coalesce(func.sum(GasLoad.kg_loaded), 0)).scalar()
    gas_used = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).join(
        FillingOperation
    ).scalar()
    available_gas = gas_total - (gas_used or 0)
    
    total_kg_needed = 0
    for detail in operation.details:
        tank_type = db.query(TankType).filter(TankType.id == detail.cylinder_type_id).first()
        kg_needed = detail.quantity * tank_type.capacity
        total_kg_needed += kg_needed
    
    if total_kg_needed > available_gas:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficiente gas. Disponible: {available_gas:.2f} kg, Necesario: {total_kg_needed:.2f} kg"
        )
    
    db_operation = FillingOperation(
        performed_by_user_id=operation.performed_by_user_id,
        notes=operation.notes
    )
    
    db.add(db_operation)
    db.flush()
    
    for detail in operation.details:
        tank_type = db.query(TankType).filter(TankType.id == detail.cylinder_type_id).first()
        kg_used = detail.quantity * tank_type.capacity
        
        db_detail = FillingOperationDetail(
            operation_id=db_operation.id,
            cylinder_type_id=detail.cylinder_type_id,
            quantity=detail.quantity,
            kg_used=kg_used
        )
        db.add(db_detail)
    
    db.commit()
    db.refresh(db_operation)
    
    print(f"[FILLING DEBUG] Operación creada ID: {db_operation.id}")
    print(f"[FILLING DEBUG] Detalles guardados: {len(db_operation.details)}")
    for d in db_operation.details:
        print(f"[FILLING DEBUG]   - tipo={d.cylinder_type_id}, cantidad={d.quantity}, kg={d.kg_used}")
    
    total_qty = sum(d.quantity for d in operation.details)
    total_kg = sum(d.quantity * db.query(TankType).filter(TankType.id == d.cylinder_type_id).first().capacity for d in operation.details)
    print(f"[FILLING] Usuario {current_user.email} embasó {total_qty} cilindros, {total_kg:.2f} kg gas usado")
    
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
        query = query.join(FillingOperation.details).filter(
            FillingOperationDetail.cylinder_type_id == cylinder_type_id
        )
    if performed_by_user_id:
        query = query.filter(FillingOperation.performed_by_user_id == performed_by_user_id)
    
    results = query.order_by(FillingOperation.date.desc()).all()
    print(f"[FILLING DEBUG] GET /filling - Total operaciones encontradas: {len(results)}")
    for op in results[:3]:
        print(f"[FILLING DEBUG]   - ID={op.id}, fecha={op.date}, detalles={len(op.details)}")
    
    return results

@router.get("/filling/summary")
def get_filling_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    results = db.query(
        FillingOperationDetail.cylinder_type_id,
        TankType.name,
        func.coalesce(func.sum(FillingOperationDetail.quantity), 0).label("total_cylinders"),
        func.coalesce(func.sum(FillingOperationDetail.kg_used), 0).label("total_kg")
    ).join(
        TankType, FillingOperationDetail.cylinder_type_id == TankType.id
    ).group_by(
        FillingOperationDetail.cylinder_type_id, TankType.name
    ).all()
    
    return [{
        "cylinder_type_id": r.cylinder_type_id,
        "name": r.name,
        "total_cylinders": r.total_cylinders,
        "total_kg": float(r.total_kg)
    } for r in results]

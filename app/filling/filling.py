from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from app.core.database.database import get_db
from app.models.models import FillingOperation, FillingOperationDetail, TankType, User, EmptyCylinderMovement, EmptyCylinderMovementDetail, GasLoad, Location, GasMovement, GasMovementStatus
from app.schemas.schemas import FillingOperation as FillingOperationSchema, FillingOperationCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

def paginate_query(query, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    total = query.count()
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    items = query.offset(offset).limit(limit).all()
    return items, total, total_pages

def get_stock_embasado(db: Session) -> float:
    embasado = db.query(Location).filter(Location.name == "Embasado").first()
    if not embasado:
        print("[FILLING] No se encontró ubicación Embasado, usando cálculo legacy")
        gas_total = db.query(func.coalesce(func.sum(GasLoad.kg_loaded), 0)).scalar() or 0
        gas_used = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).scalar() or 0
        return float(gas_total) - float(gas_used)
    
    kg_in = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.to_location_id == embasado.id,
        GasMovement.status == GasMovementStatus.COMPLETADO,
        GasMovement.is_initial_adjustment == False
    ).scalar() or 0
    
    kg_out = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.from_location_id == embasado.id,
        GasMovement.status == GasMovementStatus.COMPLETADO
    ).scalar() or 0
    
    filling_used = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).scalar() or 0
    
    stock = float(kg_in) - float(kg_out) - float(filling_used)
    
    print(f"[FILLING] Stock Embasado: kg_in={kg_in}, kg_out={kg_out}, filling_used={filling_used}, stock={stock}")
    
    return stock

@router.get("/inventory/embasado")
def get_embasado_stock(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    stock = get_stock_embasado(db)
    embasado = db.query(Location).filter(Location.name == "Embasado").first()
    max_capacity = embasado.max_capacity_kg if embasado else 0
    
    return {
        "stock_kg": round(stock, 2),
        "max_capacity_kg": max_capacity,
        "utilization_percentage": round((stock / max_capacity * 100) if max_capacity > 0 else 0, 2)
    }

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
                detail=f"No hay suficientes cilindros vacíos para tipo {tank_type.name}. Disponibles: {available_empty}, Solicitados: {detail.quantity}"
            )
    
    stock_embasado = get_stock_embasado(db)
    
    total_kg_needed = 0
    for detail in operation.details:
        tank_type = db.query(TankType).filter(TankType.id == detail.cylinder_type_id).first()
        kg_needed = detail.quantity * tank_type.capacity
        total_kg_needed += kg_needed
    
    print(f"[FILLING] Stock Embasado: {stock_embasado:.2f} kg, Kg requeridos: {total_kg_needed:.2f} kg")
    
    if total_kg_needed > stock_embasado:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficiente gas en Embasado. Disponible: {stock_embasado:.2f} kg, Necesario: {total_kg_needed:.2f} kg"
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

@router.get("/filling")
def get_filling_operations(
    cylinder_type_id: int = None,
    performed_by_user_id: int = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
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
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(FillingOperation.date >= start)
        except:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(FillingOperation.date <= end)
        except:
            pass
    
    query = query.options(
        joinedload(FillingOperation.details).joinedload(FillingOperationDetail.cylinder_type)
    )
    query = query.order_by(FillingOperation.date.desc())
    
    items, total, total_pages = paginate_query(query, page, limit)
    
    print(f"[FILLING DEBUG] page={page}, limit={limit}, total={total}")
    for op in items:
        print(f"[FILLING DEBUG]   - ID={op.id}, details={len(op.details) if op.details else 0}")
    
    return {
        "data": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

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

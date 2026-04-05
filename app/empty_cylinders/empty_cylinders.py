from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from app.core.database.database import get_db
from app.models.models import EmptyCylinderMovement, EmptyCylinderMovementDetail, TankType, User
from app.schemas.schemas import EmptyCylinderMovement as EmptyCylinderMovementSchema, EmptyCylinderMovementCreate, PaginatedResponse
from app.auth.auth import get_current_active_user

router = APIRouter()

def paginate_query(query, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    total = query.count()
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    items = query.offset(offset).limit(limit).all()
    return items, total, total_pages

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

@router.get("/empty-cylinders")
def get_empty_cylinder_movements(
    cylinder_type_id: int = None,
    source: str = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
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
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(EmptyCylinderMovement.date >= start)
        except:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(EmptyCylinderMovement.date <= end)
        except:
            pass
    
    query = query.options(
        joinedload(EmptyCylinderMovement.details).joinedload(EmptyCylinderMovementDetail.cylinder_type)
    )
    query = query.order_by(EmptyCylinderMovement.date.desc())
    
    items, total, total_pages = paginate_query(query, page, limit)
    
    print(f"[EMPTY_CYLINDERS DEBUG] page={page}, limit={limit}, total={total}, items={len(items)}")
    for m in items:
        print(f"[EMPTY_CYLINDERS DEBUG]   - ID={m.id}, details_loaded={len(m.details) if m.details else 'not loaded'}")
    
    return {
        "data": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

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

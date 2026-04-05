from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from app.core.database.database import get_db
from app.models.models import GasLoad, User
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
    
    db_gas_load = GasLoad(
        kg_loaded=gas_load.kg_loaded,
        vehicle_plate=gas_load.vehicle_plate,
        received_by_user_id=gas_load.received_by_user_id,
        notes=gas_load.notes
    )
    
    db.add(db_gas_load)
    db.commit()
    db.refresh(db_gas_load)
    
    print(f"[GAS_LOADS] Usuario {current_user.email} registró carga de {gas_load.kg_loaded:.2f} kg de gas, vehículo: {gas_load.vehicle_plate or 'N/A'}")
    
    return db_gas_load

@router.get("/gas-loads")
def get_gas_loads(
    received_by_user_id: int = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(GasLoad)
    
    if received_by_user_id:
        query = query.filter(GasLoad.received_by_user_id == received_by_user_id)
    
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
    
    print(f"[GAS_LOADS DEBUG] page={page}, limit={limit}, total={total}")
    for g in items[:3]:
        print(f"[GAS_LOADS DEBUG]   - ID={g.id}, kg={g.kg_loaded}, fecha={g.date}")
    
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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.core.database.database import get_db
from app.models.models import Jornada, JornadaShift, JornadaStatus, Sale, TankType, InventoryLocation, Debt, User, UserRole
from app.schemas.schemas import (
    Jornada as JornadaSchema,
    JornadaCreate,
    JornadaUpdate,
    Sale as SaleSchema,
    SaleCreate,
    CloseJornadaRequest,
    AssignDebtRequest,
    Debt as DebtSchema
)
from app.auth.auth import get_current_active_user
from app.tank_types.tank_types import require_role

router = APIRouter()

@router.get("/jornadas", response_model=List[JornadaSchema])
def get_jornadas(
    status: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    query = db.query(Jornada).join(User)
    if status:
        query = query.filter(Jornada.status == status)
    return query.order_by(Jornada.date.desc()).offset(skip).limit(limit).all()

@router.post("/jornadas", response_model=JornadaSchema)
def create_jornada(
    jornada: JornadaCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["admin", "superadmin"]))
):
    seller = db.query(User).filter(
        User.id == jornada.seller_id,
        User.role == UserRole.VENDEDOR.value
    ).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")
    
    db_jornada = Jornada(
        shift=jornada.shift,
        seller_id=jornada.seller_id,
        status=JornadaStatus.ABIERTA
    )
    db.add(db_jornada)
    db.commit()
    db.refresh(db_jornada)
    return db_jornada

@router.get("/jornadas/{jornada_id}", response_model=JornadaSchema)
def get_jornada(
    jornada_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    return jornada

@router.get("/jornadas/{jornada_id}/sales", response_model=List[SaleSchema])
def get_jornada_sales(
    jornada_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    
    return db.query(Sale).filter(Sale.jornada_id == jornada_id).all()

@router.put("/jornadas/{jornada_id}/close", response_model=JornadaSchema)
def close_jornada(
    jornada_id: int,
    request: CloseJornadaRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["admin", "superadmin"]))
):
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    
    if jornada.status == JornadaStatus.CERRADA:
        raise HTTPException(status_code=400, detail="La jornada ya está cerrada")
    
    sales = db.query(Sale).filter(Sale.jornada_id == jornada_id).all()
    total_sales = sum(sale.total for sale in sales)
    
    jornada.total_sales = total_sales
    jornada.total_money = request.total_money
    jornada.status = JornadaStatus.CERRADA
    
    db.commit()
    db.refresh(jornada)
    return jornada

@router.get("/jornadas/open")
def get_open_jornada(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if current_user.role != UserRole.VENDEDOR:
        raise HTTPException(status_code=403, detail="Solo vendedores tienen jornadas abiertas")
    
    jornada = db.query(Jornada).filter(
        Jornada.seller_id == current_user.id,
        Jornada.status == JornadaStatus.ABIERTA
    ).first()
    
    if not jornada:
        raise HTTPException(status_code=404, detail="No hay jornada abierta")
    
    return jornada

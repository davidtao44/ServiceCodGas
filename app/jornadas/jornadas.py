from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
from app.core.database.database import get_db
from app.models.models import (
    Jornada, JornadaShift, JornadaStatus, Sale, TankType, 
    InventoryLocation, Debt, User, UserRole
)
from app.schemas.schemas import (
    Jornada as JornadaSchema,
    JornadaCreate,
    JornadaUpdate,
    JornadaCierre,
    Sale as SaleSchema,
    SaleCreate,
    Debt as DebtSchema
)
from app.auth.auth import get_current_active_user
from app.tank_types.tank_types import require_role

router = APIRouter()

def get_next_shift(current_shift: str) -> str:
    shifts = {"mañana": "tarde", "tarde": "noche", "noche": "mañana"}
    return shifts.get(current_shift, "mañana")

def auto_open_jornada(db: Session, shift: str, seller_id: int) -> Jornada:
    if isinstance(shift, JornadaShift):
        shift = shift.value
    
    existing = db.query(Jornada).filter(
        Jornada.shift == shift,
        Jornada.status == JornadaStatus.ABIERTA.value
    ).first()
    
    if existing:
        return existing
    
    db_jornada = Jornada(
        shift=shift,
        seller_id=seller_id,
        status=JornadaStatus.ABIERTA.value,
        hora_inicio=datetime.utcnow()
    )
    db.add(db_jornada)
    db.commit()
    db.refresh(db_jornada)
    return db_jornada

@router.get("/jornadas", response_model=List[JornadaSchema])
def get_jornadas(
    status: Optional[str] = None,
    shift: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    query = db.query(Jornada).join(User)
    if status:
        query = query.filter(Jornada.status == status)
    if shift:
        query = query.filter(Jornada.shift == shift)
    return query.order_by(Jornada.date.desc()).offset(skip).limit(limit).all()

@router.get("/jornadas/activas", response_model=List[JornadaSchema])
def get_active_jornadas(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    return db.query(Jornada).filter(
        Jornada.status == JornadaStatus.ABIERTA.value
    ).order_by(Jornada.shift).all()

@router.get("/jornadas/open", response_model=JornadaSchema)
def get_open_jornada(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if current_user.role not in [UserRole.VENDEDOR.value, "vendedor"]:
        raise HTTPException(status_code=403, detail="Solo vendedores tienen jornadas")
    
    jornada = db.query(Jornada).filter(
        Jornada.seller_id == current_user.id,
        Jornada.status == JornadaStatus.ABIERTA.value
    ).first()
    
    if not jornada:
        raise HTTPException(status_code=404, detail="No hay jornada abierta")
    
    return jornada

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
    
    shift_value = jornada.shift.value if isinstance(jornada.shift, JornadaShift) else jornada.shift
    
    db_jornada = Jornada(
        shift=shift_value,
        seller_id=jornada.seller_id,
        status=JornadaStatus.ABIERTA.value,
        hora_inicio=datetime.utcnow()
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

@router.put("/jornadas/{jornada_id}/cerrar", response_model=JornadaSchema)
def close_jornada(
    jornada_id: int,
    request: JornadaCierre,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if current_user.role not in [UserRole.VENDEDOR.value, "vendedor"]:
        raise HTTPException(status_code=403, detail="Solo vendedores pueden cerrar jornadas")
    
    jornada = db.query(Jornada).filter(
        Jornada.id == jornada_id,
        Jornada.seller_id == current_user.id
    ).first()
    
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    
    current_status = jornada.status if isinstance(jornada.status, str) else jornada.status.value
    if current_status == "cerrada":
        raise HTTPException(status_code=400, detail="La jornada ya está cerrada")
    
    if current_status == "confirmada":
        raise HTTPException(status_code=400, detail="La jornada ya está confirmada")
    
    sales = db.query(Sale).filter(Sale.jornada_id == jornada_id).all()
    total_sales = sum(sale.total for sale in sales)
    
    total_gastos = 0.0
    if request.gastos:
        total_gastos = sum(request.gastos.values())
    
    jornada.hora_fin = datetime.utcnow()
    jornada.status = JornadaStatus.CERRADA.value
    jornada.total_sales = total_sales
    jornada.total_gastos = total_gastos
    jornada.dinero = request.dinero
    
    if request.cylinders_vacios:
        jornada.cylinders_vacios = json.dumps(request.cylinders_vacios)
    if request.cylinders_llenos:
        jornada.cylinders_llenos = json.dumps(request.cylinders_llenos)
    if request.gastos:
        jornada.gastos = json.dumps(request.gastos)
    
    db.commit()
    db.refresh(jornada)
    return jornada

@router.put("/jornadas/{jornada_id}/confirmar", response_model=JornadaSchema)
def confirmar_jornada(
    jornada_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["admin", "superadmin"]))
):
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    
    current_status = jornada.status if isinstance(jornada.status, str) else jornada.status.value
    if current_status != "cerrada":
        raise HTTPException(status_code=400, detail="La jornada debe estar cerrada para confirmar")
    
    jornada.status = JornadaStatus.CONFIRMADA.value
    
    db.commit()
    db.refresh(jornada)
    return jornada

@router.put("/jornadas/{jornada_id}/rechazar", response_model=JornadaSchema)
def rechazar_jornada(
    jornada_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["admin", "superadmin"]))
):
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    
    current_status = jornada.status if isinstance(jornada.status, str) else jornada.status.value
    if current_status != "cerrada":
        raise HTTPException(status_code=400, detail="La jornada debe estar cerrada para rechazar")
    
    jornada.status = JornadaStatus.ABIERTA.value
    jornada.hora_fin = None
    jornada.dinero = 0.0
    jornada.cylinders_vacios = None
    jornada.cylinders_llenos = None
    jornada.gastos = None
    jornada.total_sales = 0.0
    jornada.total_gastos = 0.0
    
    db.commit()
    db.refresh(jornada)
    return jornada

@router.get("/jornadas/{jornada_id}/detalle")
def get_jornada_detalle(
    jornada_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    
    sales = db.query(Sale).filter(Sale.jornada_id == jornada_id).all()
    seller = db.query(User).filter(User.id == jornada.seller_id).first()
    
    cylinders_vacios = None
    cylinders_llenos = None
    gastos = None
    
    if jornada.cylinders_vacios:
        try:
            cylinders_vacios = json.loads(jornada.cylinders_vacios)
        except:
            pass
    
    if jornada.cylinders_llenos:
        try:
            cylinders_llenos = json.loads(jornada.cylinders_llenos)
        except:
            pass
    
    if jornada.gastos:
        try:
            gastos = json.loads(jornada.gastos)
        except:
            pass
    
    return {
        "id": jornada.id,
        "date": jornada.date,
        "shift": jornada.shift if isinstance(jornada.shift, str) else jornada.shift.value,
        "status": jornada.status if isinstance(jornada.status, str) else jornada.status.value,
        "hora_inicio": jornada.hora_inicio,
        "hora_fin": jornada.hora_fin,
        "seller": {
            "id": seller.id,
            "name": f"{seller.first_name} {seller.last_name}"
        } if seller else None,
        "cylinders_vacios": cylinders_vacios,
        "cylinders_llenos": cylinders_llenos,
        "dinero": jornada.dinero,
        "gastos": gastos,
        "total_sales": jornada.total_sales,
        "total_gastos": jornada.total_gastos,
        "sales": [
            {
                "id": s.id,
                "tank_type": s.tank_type.name if s.tank_type else None,
                "quantity": s.quantity,
                "unit_price": s.unit_price,
                "total": s.total,
                "created_at": s.created_at
            } for s in sales
        ]
    }
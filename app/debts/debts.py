from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.core.database.database import get_db
from app.models.models import Debt, DebtStatus, UserRole
from app.schemas.schemas import Debt as DebtSchema, AssignDebtRequest
from app.auth.auth import get_current_active_user
from app.tank_types.tank_types import require_role

router = APIRouter()

@router.get("/debts", response_model=List[DebtSchema])
def get_debts(
    status: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    query = db.query(Debt)
    if status:
        query = query.filter(Debt.status == status)
    return query.order_by(Debt.assigned_at.desc()).all()

@router.get("/debts/seller/{seller_id}", response_model=List[DebtSchema])
def get_seller_debts(
    seller_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    return db.query(Debt).filter(Debt.seller_id == seller_id).all()

@router.post("/debts/jornada/{jornada_id}/assign", response_model=DebtSchema)
def assign_debt(
    jornada_id: int,
    request: AssignDebtRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["admin", "superadmin"]))
):
    from app.models.models import Jornada, User
    
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    
    if jornada.total_money >= jornada.total_sales:
        raise HTTPException(status_code=400, detail="La jornada no tiene deuda")
    
    debt_amount = jornada.total_sales - jornada.total_money
    
    seller = db.query(User).filter(User.id == request.seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")
    
    db_debt = Debt(
        jornada_id=jornada_id,
        seller_id=request.seller_id,
        amount=debt_amount,
        status=DebtStatus.PENDIENTE
    )
    db.add(db_debt)
    db.commit()
    db.refresh(db_debt)
    
    return db_debt

@router.put("/debts/{debt_id}/pay", response_model=DebtSchema)
def pay_debt(
    debt_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["admin", "superadmin"]))
):
    debt = db.query(Debt).filter(Debt.id == debt_id).first()
    if not debt:
        raise HTTPException(status_code=404, detail="Deuda no encontrada")
    
    if debt.status == DebtStatus.PAGADA:
        raise HTTPException(status_code=400, detail="La deuda ya está pagada")
    
    debt.status = DebtStatus.PAGADA
    debt.paid_at = datetime.utcnow()
    
    db.commit()
    db.refresh(debt)
    
    return debt

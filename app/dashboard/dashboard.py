from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database.database import get_db
from app.models.models import GasTank, Inventory, Transaction, User, TankStatus
from app.schemas.schemas import DashboardStats, Transaction as TransactionSchema
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    total_tanks = db.query(GasTank).count()
    available_tanks = db.query(GasTank).filter(GasTank.current_status == TankStatus.AVAILABLE).count()
    low_stock_items = db.query(Inventory).filter(
        Inventory.quantity_available <= Inventory.minimum_stock
    ).count()
    
    recent_transactions = db.query(Transaction).join(GasTank).join(User).order_by(
        Transaction.timestamp.desc()
    ).limit(10).all()
    
    return DashboardStats(
        total_tanks=total_tanks,
        available_tanks=available_tanks,
        low_stock_items=low_stock_items,
        recent_transactions=recent_transactions
    )

@router.get("/dashboard/low-stock")
def get_low_stock_items(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    return db.query(Inventory).join(GasTank).join(GasTank.tank_type).filter(
        Inventory.quantity_available <= Inventory.minimum_stock
    ).all()

@router.get("/dashboard/tank-status-summary")
def get_tank_status_summary(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    return db.query(
        GasTank.current_status,
        func.count(GasTank.id).label('count')
    ).group_by(GasTank.current_status).all()
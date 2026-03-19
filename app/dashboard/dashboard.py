from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database.database import get_db
from app.models.models import TankType, InventoryLocation, Jornada, JornadaStatus, Debt, DebtStatus, Sale
from app.schemas.schemas import DashboardStats, Sale as SaleSchema
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    total_tank_types = db.query(TankType).filter(TankType.is_active == True).count()
    
    planta_total = db.query(func.sum(InventoryLocation.quantity)).filter(
        InventoryLocation.location == "planta"
    ).scalar() or 0
    
    venta_total = db.query(func.sum(InventoryLocation.quantity)).filter(
        InventoryLocation.location == "venta"
    ).scalar() or 0
    
    open_jornadas = db.query(Jornada).filter(
        Jornada.status == JornadaStatus.ABIERTA
    ).count()
    
    pending_debts = db.query(func.sum(Debt.amount)).filter(
        Debt.status == DebtStatus.PENDIENTE
    ).scalar() or 0.0
    
    recent_sales = db.query(Sale).order_by(Sale.created_at.desc()).limit(10).all()
    
    return DashboardStats(
        total_tank_types=total_tank_types,
        total_inventory_planta=planta_total,
        total_inventory_venta=venta_total,
        open_jornadas=open_jornadas,
        pending_debts=pending_debts,
        recent_sales=recent_sales
    )

@router.get("/dashboard/low-stock")
def get_low_stock_items(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    tank_types = db.query(TankType).filter(TankType.is_active == True).all()
    
    low_stock = []
    for tt in tank_types:
        venta = db.query(InventoryLocation).filter(
            InventoryLocation.tank_type_id == tt.id,
            InventoryLocation.location == "venta"
        ).first()
        
        if venta and venta.quantity < 5:
            low_stock.append({
                "tank_type": tt.name,
                "quantity": venta.quantity,
                "location": "venta"
            })
    
    return low_stock

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database.database import get_db
from app.models.models import Sale, Jornada, TankType, InventoryLocation, UserRole
from app.schemas.schemas import Sale as SaleSchema, SaleCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.post("/ventas", response_model=SaleSchema)
def register_sale(
    sale: SaleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if current_user.role != UserRole.VENDEDOR:
        raise HTTPException(status_code=403, detail="Solo vendedores pueden registrar ventas")
    
    jornada = db.query(Jornada).filter(
        Jornada.id == sale.jornada_id,
        Jornada.seller_id == current_user.id
    ).first()
    
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada o no te pertenece")
    
    if jornada.status.value != "abierta":
        raise HTTPException(status_code=400, detail="La jornada está cerrada")
    
    tank_type = db.query(TankType).filter(TankType.id == sale.tank_type_id).first()
    if not tank_type:
        raise HTTPException(status_code=404, detail="Tipo de cilindro no encontrado")
    
    venta_inventory = db.query(InventoryLocation).filter(
        InventoryLocation.tank_type_id == sale.tank_type_id,
        InventoryLocation.location == "venta"
    ).first()
    
    if not venta_inventory or venta_inventory.quantity < sale.quantity:
        raise HTTPException(status_code=400, detail="No hay suficiente inventario en venta")
    
    venta_inventory.quantity -= sale.quantity
    
    db_sale = Sale(
        jornada_id=sale.jornada_id,
        tank_type_id=sale.tank_type_id,
        quantity=sale.quantity,
        unit_price=tank_type.price,
        total=tank_type.price * sale.quantity
    )
    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)
    
    return db_sale

@router.get("/ventas/jornada/{jornada_id}", response_model=List[SaleSchema])
def get_jornada_sales(
    jornada_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    return db.query(Sale).filter(Sale.jornada_id == jornada_id).all()

@router.get("/ventas/tank-types")
def get_tank_types_for_sale(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    tank_types = db.query(TankType).filter(TankType.is_active == True).all()
    
    result = []
    for tt in tank_types:
        venta = db.query(InventoryLocation).filter(
            InventoryLocation.tank_type_id == tt.id,
            InventoryLocation.location == "venta"
        ).first()
        
        result.append({
            "id": tt.id,
            "name": tt.name,
            "capacity": tt.capacity,
            "price": tt.price,
            "available": venta.quantity if venta else 0
        })
    
    return result

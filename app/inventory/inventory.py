from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database.database import get_db
from app.models.models import InventoryLocation, TankType, UserRole
from app.schemas.schemas import (
    InventoryLocation as InventoryLocationSchema,
    InventoryLocationCreate,
    InventoryLocationUpdate,
    InventoryLocationBase
)
from app.auth.auth import get_current_active_user
from app.tank_types.tank_types import require_role

router = APIRouter()

@router.get("/inventory", response_model=List[InventoryLocationSchema])
def get_inventory(
    location: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    query = db.query(InventoryLocation).join(TankType)
    if location:
        query = query.filter(InventoryLocation.location == location)
    return query.all()

@router.get("/inventory/planta", response_model=List[InventoryLocationSchema])
def get_inventory_planta(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    return db.query(InventoryLocation).join(TankType).filter(
        InventoryLocation.location == "planta"
    ).all()

@router.get("/inventory/venta", response_model=List[InventoryLocationSchema])
def get_inventory_venta(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    return db.query(InventoryLocation).join(TankType).filter(
        InventoryLocation.location == "venta"
    ).all()

@router.put("/inventory/{inventory_id}", response_model=InventoryLocationSchema)
def update_inventory(
    inventory_id: int,
    inventory_update: InventoryLocationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["superadmin", "admin"]))
):
    inventory = db.query(InventoryLocation).filter(InventoryLocation.id == inventory_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")
    
    update_data = inventory_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(inventory, field, value)
    
    db.commit()
    db.refresh(inventory)
    return inventory

@router.post("/inventory/initialize")
def initialize_inventory(
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["superadmin", "admin"]))
):
    tank_types = db.query(TankType).filter(TankType.is_active == True).all()
    
    created = []
    for tank_type in tank_types:
        planta_exists = db.query(InventoryLocation).filter(
            InventoryLocation.tank_type_id == tank_type.id,
            InventoryLocation.location == "planta"
        ).first()
        
        venta_exists = db.query(InventoryLocation).filter(
            InventoryLocation.tank_type_id == tank_type.id,
            InventoryLocation.location == "venta"
        ).first()
        
        if not planta_exists:
            planta = InventoryLocation(
                tank_type_id=tank_type.id,
                location="planta",
                quantity=0
            )
            db.add(planta)
            created.append(f"planta - {tank_type.name}")
        
        if not venta_exists:
            venta = InventoryLocation(
                tank_type_id=tank_type.id,
                location="venta",
                quantity=0
            )
            db.add(venta)
            created.append(f"venta - {tank_type.name}")
    
    db.commit()
    return {"message": "Inventario inicializado", "created": created}

@router.get("/inventory/summary")
def get_inventory_summary(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    tank_types = db.query(TankType).filter(TankType.is_active == True).all()
    
    summary = []
    for tt in tank_types:
        planta = db.query(InventoryLocation).filter(
            InventoryLocation.tank_type_id == tt.id,
            InventoryLocation.location == "planta"
        ).first()
        
        venta = db.query(InventoryLocation).filter(
            InventoryLocation.tank_type_id == tt.id,
            InventoryLocation.location == "venta"
        ).first()
        
        summary.append({
            "tank_type_id": tt.id,
            "tank_type_name": tt.name,
            "capacity": tt.capacity,
            "price": tt.price,
            "planta": planta.quantity if planta else 0,
            "venta": venta.quantity if venta else 0,
            "total": (planta.quantity if planta else 0) + (venta.quantity if venta else 0)
        })
    
    return summary

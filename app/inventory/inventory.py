from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database.database import get_db
from app.models.models import GasTank, GasTankType, Inventory, Transaction, TransactionType
from app.schemas.schemas import GasTank as GasTankSchema, GasTankCreate, GasTankUpdate, Inventory as InventorySchema, InventoryCreate, InventoryUpdate, Transaction as TransactionSchema, TransactionCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.get("/tanks", response_model=List[GasTankSchema])
def get_tanks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    query = db.query(GasTank).join(GasTankType)
    if status:
        query = query.filter(GasTank.current_status == status)
    return query.offset(skip).limit(limit).all()

@router.post("/tanks", response_model=GasTankSchema)
def create_tank(
    tank: GasTankCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if current_user.role.value not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_tank = GasTank(**tank.dict())
    db.add(db_tank)
    db.commit()
    db.refresh(db_tank)
    
    inventory = Inventory(tank_id=db_tank.id, quantity_available=0, updated_by=current_user.id)
    db.add(inventory)
    db.commit()
    
    return db_tank

@router.get("/tanks/{tank_id}", response_model=GasTankSchema)
def get_tank(tank_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    tank = db.query(GasTank).filter(GasTank.id == tank_id).first()
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")
    return tank

@router.put("/tanks/{tank_id}", response_model=GasTankSchema)
def update_tank(
    tank_id: int,
    tank_update: GasTankUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if current_user.role.value not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    tank = db.query(GasTank).filter(GasTank.id == tank_id).first()
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")
    
    update_data = tank_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tank, field, value)
    
    db.commit()
    db.refresh(tank)
    return tank

@router.get("/inventory", response_model=List[InventorySchema])
def get_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    low_stock: bool = Query(False),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    query = db.query(Inventory).join(GasTank).join(GasTankType)
    
    if low_stock:
        query = query.filter(Inventory.quantity_available <= Inventory.minimum_stock)
    
    return query.offset(skip).limit(limit).all()

@router.put("/inventory/{inventory_id}", response_model=InventorySchema)
def update_inventory(
    inventory_id: int,
    inventory_update: InventoryUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if current_user.role.value not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    old_quantity = inventory.quantity_available
    update_data = inventory_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(inventory, field, value)
    
    inventory.updated_by = current_user.id
    
    if "quantity_available" in update_data:
        quantity_diff = inventory.quantity_available - old_quantity
        transaction_type = TransactionType.IN if quantity_diff > 0 else TransactionType.OUT
        
        transaction = Transaction(
            tank_id=inventory.tank_id,
            transaction_type=transaction_type,
            quantity=abs(quantity_diff),
            user_id=current_user.id,
            notes=f"Inventory adjustment: {quantity_diff:+d}"
        )
        db.add(transaction)
    
    db.commit()
    db.refresh(inventory)
    return inventory

@router.post("/transactions", response_model=TransactionSchema)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if current_user.role.value not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    inventory = db.query(Inventory).filter(Inventory.tank_id == transaction.tank_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Tank inventory not found")
    
    if transaction.transaction_type == TransactionType.OUT:
        if inventory.quantity_available < transaction.quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        inventory.quantity_available -= transaction.quantity
    else:
        inventory.quantity_available += transaction.quantity
    
    inventory.updated_by = current_user.id
    
    db_transaction = Transaction(
        **transaction.dict(),
        user_id=current_user.id
    )
    
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    
    return db_transaction

@router.get("/transactions", response_model=List[TransactionSchema])
def get_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tank_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    query = db.query(Transaction).join(GasTank).join(GasTankType)
    
    if tank_id:
        query = query.filter(Transaction.tank_id == tank_id)
    
    return query.order_by(Transaction.timestamp.desc()).offset(skip).limit(limit).all()
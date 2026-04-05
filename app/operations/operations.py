from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database.database import get_db
from app.models.models import TankType, EmptyCylinderMovement, FillingOperation, FullCylinderOutput, GasLoad, User
from app.schemas.schemas import OperationsInventory
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.get("/inventory", response_model=OperationsInventory)
def get_operations_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    tank_types = db.query(TankType).filter(TankType.is_active == True).all()
    
    total_empty = 0
    total_full = 0
    empty_by_type = []
    full_by_type = []
    
    for tt in tank_types:
        empty_received = db.query(func.coalesce(func.sum(EmptyCylinderMovement.quantity), 0)).filter(
            EmptyCylinderMovement.cylinder_type_id == tt.id
        ).scalar()
        
        filled = db.query(func.coalesce(func.sum(FillingOperation.quantity), 0)).filter(
            FillingOperation.cylinder_type_id == tt.id
        ).scalar()
        
        outputs = db.query(func.coalesce(func.sum(FullCylinderOutput.quantity), 0)).filter(
            FullCylinderOutput.cylinder_type_id == tt.id
        ).scalar()
        
        empty_available = empty_received - filled
        full_available = filled - outputs
        
        total_empty += empty_available
        total_full += full_available
        
        empty_by_type.append({
            "cylinder_type_id": tt.id,
            "name": tt.name,
            "capacity": tt.capacity,
            "quantity": empty_available
        })
        
        full_by_type.append({
            "cylinder_type_id": tt.id,
            "name": tt.name,
            "capacity": tt.capacity,
            "quantity": full_available
        })
    
    gas_total = db.query(func.coalesce(func.sum(GasLoad.kg_loaded), 0)).scalar()
    gas_used = db.query(func.coalesce(func.sum(FillingOperation.kg_used), 0)).scalar()
    gas_available = gas_total - gas_used
    
    return OperationsInventory(
        empty=total_empty,
        full=total_full,
        gas=float(gas_available),
        empty_by_type=empty_by_type,
        full_by_type=full_by_type
    )

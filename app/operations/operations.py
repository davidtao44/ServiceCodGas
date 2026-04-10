from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database.database import get_db
from app.models.models import TankType, EmptyCylinderMovement, EmptyCylinderMovementDetail, FillingOperation, FillingOperationDetail, FullCylinderOutput, FullCylinderOutputDetail, GasLoad, User, Location, GasMovement, GasMovementStatus
from app.schemas.schemas import OperationsInventory
from app.auth.auth import get_current_active_user

router = APIRouter()

def calculate_gas_available(db: Session) -> float:
    embasado = db.query(Location).filter(Location.name == "Embasado").first()
    if not embasado:
        gas_total = db.query(func.coalesce(func.sum(GasLoad.kg_loaded), 0)).scalar() or 0
        gas_used = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).scalar() or 0
        return max(float(gas_total) - float(gas_used), 0)
    
    latest_movement = db.query(GasMovement).filter(
        GasMovement.to_location_id == embasado.id,
        GasMovement.status == GasMovementStatus.COMPLETADO,
        GasMovement.is_initial_adjustment == False
    ).order_by(GasMovement.date.desc()).first()
    
    active_batch_id = latest_movement.batch_id if latest_movement else None
    
    if not active_batch_id:
        return 0.0
    
    kg_in = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.batch_id == active_batch_id,
        GasMovement.is_initial_adjustment == False
    ).scalar() or 0
    
    kg_used = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).filter(
        FillingOperationDetail.batch_id == active_batch_id
    ).scalar() or 0
    
    stock = float(kg_in) - float(kg_used)
    stock_visible = max(stock, 0)
    
    print(f"[INVENTORY] Embasado batch {active_batch_id}: kg_in={kg_in}, kg_used={kg_used}, stock={stock_visible}")
    
    return stock_visible

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
    
    print(f"[INVENTORY DEBUG] Tank types encontrados: {len(tank_types)}")
    
    for tt in tank_types:
        empty_received = db.query(func.coalesce(func.sum(EmptyCylinderMovementDetail.quantity), 0)).join(
            EmptyCylinderMovement,
            EmptyCylinderMovementDetail.movement_id == EmptyCylinderMovement.id
        ).filter(
            EmptyCylinderMovementDetail.cylinder_type_id == tt.id
        ).scalar() or 0
        
        filled = db.query(func.coalesce(func.sum(FillingOperationDetail.quantity), 0)).join(
            FillingOperation,
            FillingOperationDetail.operation_id == FillingOperation.id
        ).filter(
            FillingOperationDetail.cylinder_type_id == tt.id
        ).scalar() or 0
        
        outputs = db.query(func.coalesce(func.sum(FullCylinderOutputDetail.quantity), 0)).join(
            FullCylinderOutput,
            FullCylinderOutputDetail.output_id == FullCylinderOutput.id
        ).filter(
            FullCylinderOutputDetail.cylinder_type_id == tt.id
        ).scalar() or 0
        
        empty_available = empty_received - filled
        full_available = filled - outputs
        
        print(f"[INVENTORY DEBUG] {tt.name}: vacios={empty_received}, llenados={filled}, salidas={outputs}, disponibles={empty_available}, llenos={full_available}")
        
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
    
    gas_available = calculate_gas_available(db)
    
    print(f"[INVENTORY DEBUG] Gas disponible (nuevo cálculo): {gas_available}")
    
    return OperationsInventory(
        empty=total_empty,
        full=total_full,
        gas=gas_available,
        empty_by_type=empty_by_type,
        full_by_type=full_by_type
    )

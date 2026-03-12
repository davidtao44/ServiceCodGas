from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database.database import get_db
from app.models.models import InventoryLocation, TankType, UserRole
from app.schemas.schemas import EmbasadoRequest, EmbasadoResponse
from app.auth.auth import get_current_active_user
from app.tank_types.tank_types import require_role

router = APIRouter()

@router.post("/embasado", response_model=EmbasadoResponse)
def register_embasado(
    request: EmbasadoRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["embasador"]))
):
    tank_type = db.query(TankType).filter(TankType.id == request.tank_type_id).first()
    if not tank_type:
        raise HTTPException(status_code=404, detail="Tipo de cilindro no encontrado")
    
    planta = db.query(InventoryLocation).filter(
        InventoryLocation.tank_type_id == request.tank_type_id,
        InventoryLocation.location == "planta"
    ).first()
    
    venta = db.query(InventoryLocation).filter(
        InventoryLocation.tank_type_id == request.tank_type_id,
        InventoryLocation.location == "venta"
    ).first()
    
    if not planta or not venta:
        raise HTTPException(status_code=400, detail="Inventario no inicializado para este tipo")
    
    if planta.quantity < request.filled_quantity:
        raise HTTPException(status_code=400, detail="No hay suficientes tanques vacíos en planta")
    
    planta_before = planta.quantity
    planta.quantity -= request.filled_quantity
    planta.quantity -= request.sent_to_sale_quantity
    
    venta_before = venta.quantity
    venta.quantity += request.sent_to_sale_quantity
    
    db.commit()
    db.refresh(planta)
    db.refresh(venta)
    
    return EmbasadoResponse(
        tank_type_id=request.tank_type_id,
        location_planta_before=planta_before,
        location_planta_after=planta.quantity,
        location_venta_before=venta_before,
        location_venta_after=venta.quantity,
        filled_quantity=request.filled_quantity,
        sent_to_sale_quantity=request.sent_to_sale_quantity
    )

@router.get("/embasado/planta")
def get_planta_inventory(
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["embasador"]))
):
    return db.query(InventoryLocation).join(TankType).filter(
        InventoryLocation.location == "planta"
    ).all()

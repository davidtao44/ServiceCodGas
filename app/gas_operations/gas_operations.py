from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from app.core.database.database import get_db
from app.models.models import Location, GasMovement, GasMovementStatus, User, FillingOperationDetail, GasLoad
from app.schemas.schemas import (
    Location as LocationSchema,
    LocationCreate,
    LocationInventory,
    GasMovement as GasMovementSchema,
    GasMovementCreate,
    GasMovementReceive,
    GasMovementWithDifference,
    PaginatedResponse,
    EmbasadoFixResponse
)
from app.auth.auth import get_current_active_user

router = APIRouter()

LOCATIONS_INITIAL_DATA = [
    {"name": "Aguazul", "max_capacity_kg": 52800.0},
    {"name": "Punto de venta", "max_capacity_kg": 36000.0},
    {"name": "Embasado", "max_capacity_kg": 8640.0},
]

def paginate_query(query, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    total = query.count()
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    items = query.offset(offset).limit(limit).all()
    return items, total, total_pages

def get_location_stock(db: Session, location_id: int) -> float:
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        return 0.0
    
    if location.name == "Embasado":
        kg_in = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
            GasMovement.to_location_id == location_id,
            GasMovement.status == GasMovementStatus.COMPLETADO,
            GasMovement.is_initial_adjustment == False
        ).scalar() or 0
        
        kg_out_movements = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
            GasMovement.from_location_id == location_id,
            GasMovement.status == GasMovementStatus.COMPLETADO
        ).scalar() or 0
        
        kg_used_in_filling = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).scalar() or 0
        
        stock = float(kg_in) - float(kg_out_movements) - float(kg_used_in_filling)
        print(f"[GAS_OPS] Embasado stock: kg_in={kg_in}, kg_out={kg_out_movements}, filling={kg_used_in_filling}, stock={stock}")
        return stock
    else:
        kg_in = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
            GasMovement.to_location_id == location_id,
            GasMovement.status == GasMovementStatus.COMPLETADO
        ).scalar() or 0
        
        kg_out = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
            GasMovement.from_location_id == location_id,
            GasMovement.status == GasMovementStatus.COMPLETADO
        ).scalar() or 0
        
        return float(kg_in) - float(kg_out)

@router.post("/gas-operations/initialize-locations")
def initialize_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    created = []
    for loc_data in LOCATIONS_INITIAL_DATA:
        existing = db.query(Location).filter(Location.name == loc_data["name"]).first()
        if not existing:
            location = Location(**loc_data)
            db.add(location)
            created.append(loc_data["name"])
    
    db.commit()
    return {"message": f"Se inicializaron {len(created)} ubicaciones", "created": created}

@router.get("/locations")
def get_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    return db.query(Location).order_by(Location.id).all()

@router.post("/locations")
def create_location(
    location: LocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    existing = db.query(Location).filter(Location.name == location.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una ubicación con ese nombre")
    
    db_location = Location(**location.model_dump())
    db.add(db_location)
    db.commit()
    db.refresh(db_location)
    return db_location

@router.get("/locations/inventory")
def get_locations_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    locations = db.query(Location).order_by(Location.id).all()
    inventory = []
    
    for loc in locations:
        stock = get_location_stock(db, loc.id)
        utilization = (stock / loc.max_capacity_kg * 100) if loc.max_capacity_kg > 0 else 0
        inventory.append(LocationInventory(
            location_id=loc.id,
            location_name=loc.name,
            stock_kg=round(stock, 2),
            max_capacity_kg=loc.max_capacity_kg,
            utilization_percentage=round(utilization, 2)
        ))
    
    return inventory

@router.post("/gas-movements")
def create_gas_movement(
    movement: GasMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if movement.kg <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
    
    if movement.from_location_id and movement.to_location_id:
        if movement.from_location_id == movement.to_location_id:
            raise HTTPException(status_code=400, detail="El origen y destino no pueden ser iguales")
    
    if movement.from_location_id:
        from_stock = get_location_stock(db, movement.from_location_id)
        if movement.kg > from_stock:
            raise HTTPException(
                status_code=400,
                detail=f"No hay suficiente gas en origen. Disponible: {from_stock:.2f} kg"
            )
    
    if movement.to_location_id:
        to_location = db.query(Location).filter(Location.id == movement.to_location_id).first()
        if to_location:
            to_stock = get_location_stock(db, movement.to_location_id)
            new_stock = to_stock + movement.kg
            if new_stock > to_location.max_capacity_kg:
                raise HTTPException(
                    status_code=400,
                    detail=f"Supera capacidad del destino. Disponible: {to_location.max_capacity_kg - to_stock:.2f} kg"
                )
    
    if movement.from_location_id:
        status = GasMovementStatus.EN_TRANSITO
    else:
        status = GasMovementStatus.COMPLETADO
    
    db_movement = GasMovement(
        from_location_id=movement.from_location_id,
        to_location_id=movement.to_location_id,
        kg=movement.kg,
        status=status,
        notes=movement.notes,
        created_by=current_user.id
    )
    
    db.add(db_movement)
    db.commit()
    db.refresh(db_movement)
    
    return db_movement

@router.get("/gas-movements")
def get_gas_movements(
    from_location_id: Optional[int] = None,
    to_location_id: Optional[int] = None,
    status: Optional[GasMovementStatus] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(GasMovement)
    
    if from_location_id:
        query = query.filter(GasMovement.from_location_id == from_location_id)
    if to_location_id:
        query = query.filter(GasMovement.to_location_id == to_location_id)
    if status:
        query = query.filter(GasMovement.status == status)
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(GasMovement.date >= start)
        except:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(GasMovement.date <= end)
        except:
            pass
    
    query = query.order_by(GasMovement.date.desc())
    
    items, total, total_pages = paginate_query(query, page, limit)
    
    result = []
    for item in items:
        diff = None
        if item.status == GasMovementStatus.COMPLETADO and item.kg_arrived is not None:
            diff = item.kg - item.kg_arrived
        
        movement_dict = {
            "id": item.id,
            "date": item.date,
            "from_location_id": item.from_location_id,
            "to_location_id": item.to_location_id,
            "from_location_name": item.from_location.name if item.from_location else None,
            "to_location_name": item.to_location.name if item.to_location else None,
            "kg": item.kg,
            "kg_arrived": item.kg_arrived,
            "status": item.status.value,
            "notes": item.notes,
            "created_by": item.created_by,
            "difference": diff
        }
        result.append(movement_dict)
    
    return {
        "data": result,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

@router.get("/gas-movements/in-transit")
def get_in_transit_movements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    movements = db.query(GasMovement).filter(
        GasMovement.status == GasMovementStatus.EN_TRANSITO
    ).order_by(GasMovement.date.desc()).all()
    
    return [
        {
            "id": m.id,
            "date": m.date,
            "from_location_name": m.from_location.name if m.from_location else None,
            "to_location_name": m.to_location.name if m.to_location else None,
            "kg": m.kg,
            "notes": m.notes
        }
        for m in movements
    ]

@router.put("/gas-movements/{movement_id}/receive")
def receive_gas_movement(
    movement_id: int,
    receive_data: GasMovementReceive,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    movement = db.query(GasMovement).filter(GasMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    if movement.status != GasMovementStatus.EN_TRANSITO:
        raise HTTPException(status_code=400, detail="Este movimiento ya fue completado")
    
    if receive_data.kg_arrived < 0:
        raise HTTPException(status_code=400, detail="La cantidad llegada no puede ser negativa")
    
    movement.kg_arrived = receive_data.kg_arrived
    movement.status = GasMovementStatus.COMPLETADO
    movement.notes = (movement.notes or "") + f" | Recepción: {receive_data.kg_arrived} kg. " + (receive_data.notes or "")
    
    if movement.to_location_id:
        to_location = db.query(Location).filter(Location.id == movement.to_location_id).first()
        if to_location:
            to_stock = get_location_stock(db, movement.to_location_id)
            new_stock = to_stock + receive_data.kg_arrived
            if new_stock > to_location.max_capacity_kg:
                raise HTTPException(
                    status_code=400,
                    detail=f"Supera capacidad del destino. Capacidad disponible: {to_location.max_capacity_kg - to_stock:.2f} kg"
                )
    
    db.commit()
    db.refresh(movement)
    
    difference = movement.kg - receive_data.kg_arrived
    if difference > 0:
        print(f"[GAS_OPERATIONS] Pérdida detectada en movimiento {movement_id}: {difference:.2f} kg")
    
    return movement

@router.get("/gas-movements/{movement_id}")
def get_movement(
    movement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    movement = db.query(GasMovement).filter(GasMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    return movement

@router.post("/gas-operations/fix-embasado")
def fix_embasado_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    location = db.query(Location).filter(Location.name == "Embasado").first()
    if not location:
        raise HTTPException(status_code=404, detail="Ubicación 'Embasado' no encontrada")
    
    total_consumed = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).scalar() or 0
    total_consumed = float(total_consumed)
    
    kg_in = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.to_location_id == location.id,
        GasMovement.status == GasMovementStatus.COMPLETADO
    ).scalar() or 0
    
    kg_out = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.from_location_id == location.id,
        GasMovement.status == GasMovementStatus.COMPLETADO
    ).scalar() or 0
    
    current_stock = get_location_stock(db, location.id)
    
    print(f"[GAS_OPS] Stock Embasado: kg_in={kg_in}, kg_out={kg_out}, filling_used={total_consumed}, stock={current_stock}")
    
    return EmbasadoFixResponse(
        total_consumed_kg=total_consumed,
        adjustment_created=False,
        adjustment_id=None,
        new_stock=round(current_stock, 2),
        message=f"Stock actual: {current_stock:.2f} kg (Entradas: {kg_in}, Salidas: {kg_out}, Consumo: {total_consumed})"
    )

@router.get("/gas-operations/embasado-status")
def get_embasado_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    location = db.query(Location).filter(Location.name == "Embasado").first()
    if not location:
        raise HTTPException(status_code=404, detail="Ubicación 'Embasado' no encontrada")
    
    total_consumed = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).scalar() or 0
    total_consumed = float(total_consumed)
    
    kg_in_total = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.to_location_id == location.id,
        GasMovement.status == GasMovementStatus.COMPLETADO
    ).scalar() or 0
    kg_in_total = float(kg_in_total)
    
    kg_out_total = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.from_location_id == location.id,
        GasMovement.status == GasMovementStatus.COMPLETADO
    ).scalar() or 0
    kg_out_total = float(kg_out_total)
    
    current_stock = get_location_stock(db, location.id)
    
    return {
        "location_name": location.name,
        "max_capacity_kg": location.max_capacity_kg,
        "current_stock_kg": round(current_stock, 2),
        "total_consumed_kg": round(total_consumed, 2),
        "total_kg_in": round(kg_in_total, 2),
        "total_kg_out": round(kg_out_total, 2),
        "is_negative": current_stock < 0
    }

@router.post("/gas-operations/clear-all")
def clear_gas_operations_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Solo admins pueden ejecutar esta acción")
    
    deleted_movements = db.query(GasMovement).delete()
    db.commit()
    
    return {"message": f"Se eliminaron {deleted_movements} movimientos de gas"}

@router.get("/gas-operations/gas-summary")
def get_gas_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    locations = db.query(Location).order_by(Location.id).all()
    
    total_gas_loads = db.query(func.coalesce(func.sum(GasLoad.kg_loaded), 0)).scalar()
    total_gas_loads = float(total_gas_loads)
    
    total_filling_used = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).scalar()
    total_filling_used = float(total_filling_used)
    
    legacy_available = total_gas_loads - total_filling_used
    
    in_transit_total = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.status == GasMovementStatus.EN_TRANSITO
    ).scalar()
    in_transit_total = float(in_transit_total)
    
    summary_by_location = []
    total_new_available = 0
    
    for loc in locations:
        stock = get_location_stock(db, loc.id)
        
        kg_in = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
            GasMovement.to_location_id == loc.id,
            GasMovement.status == GasMovementStatus.COMPLETADO
        ).scalar()
        kg_in = float(kg_in)
        
        kg_out = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
            GasMovement.from_location_id == loc.id,
            GasMovement.status == GasMovementStatus.COMPLETADO
        ).scalar()
        kg_out = float(kg_out)
        
        filling_used = 0
        if loc.name == "Embasado":
            filling_used = total_filling_used
        
        in_transit_in = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
            GasMovement.to_location_id == loc.id,
            GasMovement.status == GasMovementStatus.EN_TRANSITO
        ).scalar()
        in_transit_out = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
            GasMovement.from_location_id == loc.id,
            GasMovement.status == GasMovementStatus.EN_TRANSITO
        ).scalar()
        
        summary_by_location.append({
            "location_id": loc.id,
            "location_name": loc.name,
            "max_capacity_kg": loc.max_capacity_kg,
            "stock_kg": round(stock, 2),
            "utilization_percentage": round((stock / loc.max_capacity_kg * 100) if loc.max_capacity_kg > 0 else 0, 2),
            "kg_in": round(kg_in, 2),
            "kg_out": round(kg_out, 2),
            "filling_used": round(filling_used, 2),
            "in_transit_in": round(float(in_transit_in), 2),
            "in_transit_out": round(float(in_transit_out), 2),
            "is_negative": stock < 0
        })
        
        total_new_available += max(0, stock)
    
    return {
        "legacy": {
            "total_gas_loads": round(total_gas_loads, 2),
            "total_filling_used": round(total_filling_used, 2),
            "available": round(legacy_available, 2)
        },
        "by_location": summary_by_location,
        "new_total_available": round(total_new_available, 2),
        "in_transit_total": round(in_transit_total, 2),
        "has_locations": len(locations) > 0,
        "has_movements": db.query(GasMovement).count() > 0
    }

@router.post("/gas-operations/auto-fix")
def auto_fix_and_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    location = db.query(Location).filter(Location.name == "Embasado").first()
    if not location:
        return {"message": "Ubicación Embasado no encontrada", "fixed": False}
    
    total_consumed = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).scalar() or 0
    total_consumed = float(total_consumed)
    
    kg_in = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.to_location_id == location.id,
        GasMovement.status == GasMovementStatus.COMPLETADO
    ).scalar() or 0
    
    kg_out = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.from_location_id == location.id,
        GasMovement.status == GasMovementStatus.COMPLETADO
    ).scalar() or 0
    
    current_stock = float(kg_in) - float(kg_out) - total_consumed
    
    print(f"[GAS_OPS] Stock actual: kg_in={kg_in}, kg_out={kg_out}, filling={total_consumed}, stock={current_stock}")
    
    return {
        "message": f"Stock Embasado: {current_stock:.2f} kg",
        "fixed": False,
        "kg_in": round(float(kg_in), 2),
        "kg_out": round(float(kg_out), 2),
        "filling_used": round(total_consumed, 2),
        "current_stock": round(current_stock, 2)
    }

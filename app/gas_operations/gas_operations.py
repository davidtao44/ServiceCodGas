from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, distinct
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from app.core.database.database import get_db
from app.models.models import Location, GasMovement, GasMovementStatus, User, FillingOperationDetail, GasLoad, Vehicle, Driver, GasMovementExpense, ViaticosTopup
from app.schemas.schemas import (
    Location as LocationSchema,
    LocationCreate,
    LocationInventory,
    GasMovement as GasMovementSchema,
    GasMovementCreate,
    GasMovementUpdate,
    GasMovementReceive,
    GasMovementWithDifference,
    PaginatedResponse,
    EmbasadoFixResponse,
    BatchRendimiento,
    GasMovementExpenseCreate,
    GasMovementExpensesSummary,
    ViaticosTopupCreate,
    ViaticosTopupResponse
)
from app.auth.auth import get_current_active_user
from app.filling.filling import get_stock_embasado_detailed, get_batch_rendimiento as get_batch_rendimiento_calc

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
        embasado = db.query(Location).filter(Location.name == "Embasado").first()
        
        # Obtener el batch activo (último movimiento hacia Embasado)
        latest_movement = db.query(GasMovement).filter(
            GasMovement.to_location_id == embasado.id,
            GasMovement.status == GasMovementStatus.COMPLETADO,
            GasMovement.is_initial_adjustment == False
        ).order_by(GasMovement.date.desc()).first()
        
        active_batch_id = latest_movement.batch_id if latest_movement else None
        
        # kg_in = solo movimientos del batch activo
        kg_in = 0.0
        if active_batch_id:
            kg_in = float(db.query(func.coalesce(func.sum(func.coalesce(GasMovement.kg_arrived, GasMovement.kg)), 0)).filter(
                GasMovement.to_location_id == embasado.id,
                GasMovement.batch_id == active_batch_id,
                GasMovement.status == GasMovementStatus.COMPLETADO,
                GasMovement.is_initial_adjustment == False
            ).scalar() or 0)
        
        # kg_out = movimientos desde Embasado del batch activo
        kg_out = 0.0
        if active_batch_id:
            kg_out = float(db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
                GasMovement.from_location_id == embasado.id,
                GasMovement.batch_id == active_batch_id,
                GasMovement.status == GasMovementStatus.COMPLETADO,
                GasMovement.is_initial_adjustment == False
            ).scalar() or 0)
        
        stock = kg_in - kg_out
        print(f"[GAS_OPS] Embasado stock: kg_in={kg_in}, kg_out={kg_out}, stock={stock}")
        return max(0, stock)
    else:
        kg_in = db.query(func.coalesce(func.sum(func.coalesce(GasMovement.kg_arrived, GasMovement.kg)), 0)).filter(
            GasMovement.to_location_id == location_id,
            GasMovement.status == GasMovementStatus.COMPLETADO
        ).scalar() or 0
        
        kg_out = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
            GasMovement.from_location_id == location_id,
            GasMovement.status == GasMovementStatus.COMPLETADO
        ).scalar() or 0
        
        return max(0, float(kg_in) - float(kg_out))

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
                print(f"[GAS_OPS] Advertencia: Movimiento supera capacidad estimada. Nuevo stock: {new_stock:.2f} kg, Capacidad: {to_location.max_capacity_kg:.2f} kg")
            print(f"[GAS_OPS] Permitiendo movimiento: {movement.kg:.2f} kg. Stock actual: {to_stock:.2f} kg, Nuevo stock: {new_stock:.2f} kg")
    
    if movement.from_location_id:
        status = GasMovementStatus.EN_TRANSITO
    else:
        status = GasMovementStatus.COMPLETADO
    
    embasado_location = db.query(Location).filter(Location.name == "Embasado").first()
    batch_id = movement.batch_id
    
    if movement.to_location_id and embasado_location and movement.to_location_id == embasado_location.id:
        if not batch_id:
            batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
    
    driver_id = movement.driver_id
    if movement.new_driver:
        new_driver = Driver(**movement.new_driver.model_dump())
        db.add(new_driver)
        db.flush()
        driver_id = new_driver.id
        print(f"[GAS_OPS] Nuevo conductor creado: {new_driver.name} (ID: {new_driver.id})")
    
    db_movement = GasMovement(
        from_location_id=movement.from_location_id,
        to_location_id=movement.to_location_id,
        from_custom=movement.from_custom,
        to_custom=movement.to_custom,
        batch_id=batch_id,
        vehicle_id=movement.vehicle_id,
        driver_id=driver_id,
        kg=movement.kg,
        viaticos=movement.viaticos,
        status=status,
        notes=movement.notes,
        created_by=current_user.id
    )
    
    db.add(db_movement)
    db.flush()
    
    if movement.vehicle_id and movement.to_location_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == movement.vehicle_id).first()
        if vehicle:
            to_location = db.query(Location).filter(Location.id == movement.to_location_id).first()
            if to_location:
                vehicle.location = to_location.name
                print(f"[GAS_OPS] Vehículo {vehicle.name} actualizado a ubicación: {vehicle.location}")
    
    db.commit()
    db.refresh(db_movement)
    
    return db_movement

@router.get("/gas-movements")
def get_gas_movements(
    from_location_id: Optional[int] = None,
    to_location_id: Optional[int] = None,
    status: Optional[str] = None,
    batch_id: Optional[str] = None,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(GasMovement)
    
    query = query.filter(GasMovement.is_initial_adjustment == False)
    
    if from_location_id:
        query = query.filter(GasMovement.from_location_id == from_location_id)
    if to_location_id:
        query = query.filter(GasMovement.to_location_id == to_location_id)
    if status:
        try:
            status_enum = GasMovementStatus(status)
            query = query.filter(GasMovement.status == status_enum)
        except ValueError:
            pass
    if batch_id:
        query = query.filter(GasMovement.batch_id == batch_id)
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(GasMovement.date >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            end = end.replace(hour=23, minute=59, second=59)
            query = query.filter(GasMovement.date <= end)
        except ValueError:
            pass
    
    total = query.count()
    query = query.order_by(GasMovement.date.desc())
    items = query.options(
        joinedload(GasMovement.vehicle), 
        joinedload(GasMovement.driver),
        joinedload(GasMovement.expenses),
        joinedload(GasMovement.received_by)
    ).offset(offset).limit(limit).all()
    
    print(f"[GAS_OPS] get_gas_movements: total={total}, limit={limit}, offset={offset}")
    
    result = []
    for item in items:
        diff = None
        if item.status == GasMovementStatus.COMPLETADO and item.kg_arrived is not None:
            diff = item.kg - item.kg_arrived
        
        from_display = item.from_custom if item.from_custom else (item.from_location.name if item.from_location else "Carga externa")
        to_display = item.to_custom if item.to_custom else (item.to_location.name if item.to_location else "Consumo/Salida")
        
        total_gastos = sum(exp.monto for exp in item.expenses) if item.expenses else 0
        
        movement_dict = {
            "id": item.id,
            "date": item.date,
            "from_location_id": item.from_location_id,
            "to_location_id": item.to_location_id,
            "from_custom": item.from_custom,
            "to_custom": item.to_custom,
            "from_location_name": from_display,
            "to_location_name": to_display,
            "kg": item.kg,
            "kg_arrived": item.kg_arrived,
            "viaticos": item.viaticos,
            "received_viaticos_excedente": item.received_viaticos_excedente,
            "received_by_user_id": item.received_by_user_id,
            "received_by_user_name": item.received_by.first_name + " " + item.received_by.last_name if item.received_by else None,
            "total_gastos": total_gastos,
            "saldo": (item.viaticos or 0) - total_gastos,
            "status": item.status.value,
            "notes": item.notes,
            "batch_id": item.batch_id,
            "vehicle_id": item.vehicle_id,
            "vehicle_name": item.vehicle.name if item.vehicle else None,
            "vehicle_plate": item.vehicle.plate if item.vehicle else None,
            "driver_id": item.driver_id,
            "driver_name": item.driver.name if item.driver else None,
            "created_by": item.created_by,
            "difference": diff
        }
        result.append(movement_dict)
    
    return {
        "data": result,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total
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
            "from_location_name": m.from_custom if m.from_custom else (m.from_location.name if m.from_location else None),
            "to_location_name": m.to_custom if m.to_custom else (m.to_location.name if m.to_location else None),
            "kg": m.kg,
            "driver_id": m.driver_id,
            "driver_name": m.driver.name if m.driver else None,
            "batch_id": m.batch_id,
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
    
    # Calculate viaticos balance
    viaticos_inicial = movement.viaticos or 0
    viaticos_recargas = db.query(func.coalesce(func.sum(ViaticosTopup.monto), 0)).filter(ViaticosTopup.movement_id == movement.id).scalar()
    total_gastos = db.query(func.coalesce(func.sum(GasMovementExpense.monto), 0)).filter(GasMovementExpense.movement_id == movement.id).scalar()
    viaticos_totales = viaticos_inicial + viaticos_recargas
    saldo = viaticos_totales - total_gastos
    
    if saldo > 0 and receive_data.received_by_user_id:
        movement.received_viaticos_excedente = saldo
        movement.received_by_user_id = receive_data.received_by_user_id
        print(f"[GAS_OPS] Excedente de viáticos: ${saldo:.2f} recibido por user_id: {receive_data.received_by_user_id}")
    
    if movement.to_location_id:
        to_location = db.query(Location).filter(Location.id == movement.to_location_id).first()
        if to_location:
            to_stock = get_location_stock(db, movement.to_location_id)
            new_stock = to_stock + receive_data.kg_arrived
            if new_stock > to_location.max_capacity_kg:
                print(f"[GAS_OPS] Advertencia: Recepción supera capacidad estimada. Nuevo stock: {new_stock:.2f} kg, Capacidad: {to_location.max_capacity_kg:.2f} kg")
            print(f"[GAS_OPS] Permitiendo recepción: {receive_data.kg_arrived:.2f} kg. Stock actual: {to_stock:.2f} kg, Nuevo stock: {new_stock:.2f} kg")
    
    if movement.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == movement.vehicle_id).first()
        if vehicle and movement.to_location:
            vehicle.location = movement.to_location.name
            print(f"[GAS_OPS] Vehículo {vehicle.name} actualizado a ubicación: {vehicle.location}")
    
    db.commit()
    db.refresh(movement)
    
    difference = movement.kg - receive_data.kg_arrived
    if difference > 0:
        print(f"[GAS_OPERATIONS] Pérdida detectada en movimiento {movement_id}: {difference:.2f} kg")
    
    return movement


@router.get("/gas-movements/expense-types")
def get_expense_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    types = db.query(GasMovementExpense.tipo).filter(GasMovementExpense.tipo.isnot(None)).distinct().order_by(GasMovementExpense.tipo).all()
    return {"types": [t[0] for t in types]}


@router.get("/gas-movements/{movement_id}")
def get_movement(
    movement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    movement = db.query(GasMovement).options(
        joinedload(GasMovement.from_location),
        joinedload(GasMovement.to_location),
        joinedload(GasMovement.vehicle),
        joinedload(GasMovement.driver),
        joinedload(GasMovement.received_by),
        joinedload(GasMovement.expenses),
        joinedload(GasMovement.viaticos_topups),
    ).filter(GasMovement.id == movement_id).first()
    
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    # Build response with computed fields (same as get_gas_movements)
    total_gastos = sum(exp.monto for exp in movement.expenses) if movement.expenses else 0
    viaticos_recargas = sum(t.monto for t in movement.viaticos_topups) if movement.viaticos_topups else 0
    viaticos_totales = (movement.viaticos or 0) + viaticos_recargas
    
    return {
        "id": movement.id,
        "date": movement.date,
        "from_location_id": movement.from_location_id,
        "to_location_id": movement.to_location_id,
        "from_custom": movement.from_custom,
        "to_custom": movement.to_custom,
        "from_location_name": movement.from_location.name if movement.from_location else movement.from_custom,
        "to_location_name": movement.to_location.name if movement.to_location else movement.to_custom,
        "kg": movement.kg,
        "kg_arrived": movement.kg_arrived,
        "viaticos": movement.viaticos,
        "received_viaticos_excedente": movement.received_viaticos_excedente,
        "received_by_user_id": movement.received_by_user_id,
        "received_by_user_name": movement.received_by.first_name + " " + movement.received_by.last_name if movement.received_by else None,
        "total_gastos": total_gastos,
        "viaticos_recargas": viaticos_recargas,
        "viaticos_totales": viaticos_totales,
        "saldo": viaticos_totales - total_gastos,
        "status": movement.status.value,
        "notes": movement.notes,
        "batch_id": movement.batch_id,
        "vehicle_id": movement.vehicle_id,
        "vehicle_name": movement.vehicle.name if movement.vehicle else None,
        "vehicle_plate": movement.vehicle.plate if movement.vehicle else None,
        "driver_id": movement.driver_id,
        "driver_name": movement.driver.name if movement.driver else None,
        "created_by": movement.created_by,
        "difference": movement.kg - movement.kg_arrived if movement.kg_arrived is not None else None
    }

@router.put("/gas-movements/{movement_id}", response_model=GasMovementSchema)
def update_movement(
    movement_id: int,
    data: GasMovementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    movement = db.query(GasMovement).filter(GasMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(movement, field, value)

    db.add(movement)
    db.commit()
    db.refresh(movement)

    # Cargar relaciones para el response
    movement = db.query(GasMovement).options(
        joinedload(GasMovement.from_location),
        joinedload(GasMovement.to_location),
        joinedload(GasMovement.vehicle),
        joinedload(GasMovement.driver),
    ).filter(GasMovement.id == movement_id).first()

    return movement


@router.put("/gas-movements/{movement_id}/recepcion", response_model=GasMovementSchema)
def update_recepcion(
    movement_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Actualiza solo los campos de recepción (kg_arrived, notes) sin cambiar el estado."""
    movement = db.query(GasMovement).filter(GasMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    if "kg_arrived" in data and data["kg_arrived"] is not None:
        movement.kg_arrived = float(data["kg_arrived"])

    if "notes" in data and data["notes"] is not None:
        movement.notes = data["notes"]

    db.add(movement)
    db.commit()
    db.refresh(movement)

    movement = db.query(GasMovement).options(
        joinedload(GasMovement.from_location),
        joinedload(GasMovement.to_location),
        joinedload(GasMovement.vehicle),
        joinedload(GasMovement.driver),
    ).filter(GasMovement.id == movement_id).first()

    return movement


@router.delete("/gas-movements/{movement_id}/expenses/{expense_id}")
def delete_expense(
    movement_id: int,
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    expense = db.query(GasMovementExpense).filter(
        GasMovementExpense.id == expense_id,
        GasMovementExpense.movement_id == movement_id
    ).first()
    
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    
    db.delete(expense)
    db.commit()
    
    return {"message": "Gasto eliminado correctamente"}

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

@router.get("/gas-operations/gas-available")
def get_gas_available(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    embasado = db.query(Location).filter(Location.name == "Embasado").first()
    if not embasado:
        return {"gas_available_kg": 0, "batch_id": None, "kg_in": 0, "kg_used": 0}
    
    latest_movement = db.query(GasMovement).filter(
        GasMovement.to_location_id == embasado.id,
        GasMovement.status == GasMovementStatus.COMPLETADO,
        GasMovement.is_initial_adjustment == False
    ).order_by(GasMovement.date.desc()).first()
    
    active_batch_id = latest_movement.batch_id if latest_movement else None
    
    if not active_batch_id:
        return {"gas_available_kg": 0, "batch_id": None, "kg_in": 0, "kg_used": 0}
    
    kg_in = float(db.query(func.coalesce(func.sum(func.coalesce(GasMovement.kg_arrived, GasMovement.kg)), 0)).filter(
        GasMovement.batch_id == active_batch_id,
        GasMovement.is_initial_adjustment == False
    ).scalar() or 0)
    
    kg_used = float(db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).filter(
        FillingOperationDetail.batch_id == active_batch_id
    ).scalar() or 0)
    
    stock = kg_in - kg_used
    stock_visible = max(stock, 0)
    
    print(f"[GAS_OPS] Gas disponible: batch={active_batch_id}, kg_in={kg_in}, kg_used={kg_used}, available={stock_visible}")
    
    return {
        "gas_available_kg": round(stock_visible, 2),
        "batch_id": active_batch_id,
        "kg_in": round(kg_in, 2),
        "kg_used": round(kg_used, 2)
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

@router.get("/gas-operations/batch-rendimiento")
def get_batch_rendimiento(
    batch_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    embasado_location = db.query(Location).filter(Location.name == "Embasado").first()
    if not embasado_location:
        raise HTTPException(status_code=404, detail="Ubicación Embasado no encontrada")
    
    batch_query = db.query(
        GasMovement.batch_id,
        func.min(GasMovement.date).label("fecha_primer_movimiento"),
        func.max(GasMovement.date).label("fecha_ultimo_movimiento"),
        func.sum(GasMovement.kg).label("kg_enviados"),
        func.count(GasMovement.id).label("movimientos")
    ).filter(
        GasMovement.to_location_id == embasado_location.id,
        GasMovement.batch_id.isnot(None),
        GasMovement.is_initial_adjustment == False
    )
    
    if batch_id:
        batch_query = batch_query.filter(GasMovement.batch_id == batch_id)
    
    batch_query = batch_query.group_by(GasMovement.batch_id).order_by(func.min(GasMovement.date).desc())
    
    batches = batch_query.all()
    
    results = []
    for batch in batches:
        # Usar kg_arrived si existe, sino kg (enviado) como respaldo
        kg_enviados_query = db.query(
            func.coalesce(func.sum(func.coalesce(GasMovement.kg_arrived, GasMovement.kg)), 0)
        ).filter(
            GasMovement.batch_id == batch.batch_id,
            GasMovement.is_initial_adjustment == False
        ).scalar() or 0
        kg_enviados = float(kg_enviados_query)
        
        kg_usados = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).filter(
            FillingOperationDetail.batch_id == batch.batch_id
        ).scalar() or 0
        kg_usados = float(kg_usados)
        
        cilindros_extra_query = db.query(
            func.sum(FillingOperationDetail.quantity)
        ).filter(
            FillingOperationDetail.batch_id == batch.batch_id
        ).scalar() or 0
        
        diferencia = kg_enviados - kg_usados
        rendimiento = max(0, -diferencia)
        
        results.append({
            "batch_id": batch.batch_id,
            "kg_enviados": round(kg_enviados, 2),
            "kg_usados": round(kg_usados, 2),
            "diferencia": round(diferencia, 2),
            "rendimiento": round(rendimiento, 2),
            "cilindros_extra": cilindros_extra_query,
            "fecha_primer_movimiento": batch.fecha_primer_movimiento,
            "fecha_ultimo_movimiento": batch.fecha_ultimo_movimiento,
            "movimientos": batch.movimientos
        })
    
    return results

@router.get("/gas-operations/batch-list")
def get_batch_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    embasado_location = db.query(Location).filter(Location.name == "Embasado").first()
    if not embasado_location:
        return []
    
    batches = db.query(
        GasMovement.batch_id,
        func.min(GasMovement.date).label("first_date"),
        func.sum(GasMovement.kg).label("total_kg"),
        func.count(GasMovement.id).label("movement_count")
    ).filter(
        GasMovement.to_location_id == embasado_location.id,
        GasMovement.batch_id.isnot(None),
        GasMovement.is_initial_adjustment == False
    ).group_by(GasMovement.batch_id).order_by(func.min(GasMovement.date).desc()).all()
    
    return [
        {
            "batch_id": b.batch_id,
            "first_date": b.first_date,
            "total_kg": round(float(b.total_kg), 2) if b.total_kg else 0,
            "movement_count": b.movement_count
        }
        for b in batches
    ]

@router.get("/gas-operations/active-batch")
def get_active_batch(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    embasado_location = db.query(Location).filter(Location.name == "Embasado").first()
    if not embasado_location:
        return None
    
    latest_movement = db.query(GasMovement).filter(
        GasMovement.to_location_id == embasado_location.id,
        GasMovement.batch_id.isnot(None),
        GasMovement.is_initial_adjustment == False
    ).order_by(GasMovement.date.desc()).first()
    
    if not latest_movement:
        return None
    
    kg_sent = db.query(func.coalesce(func.sum(GasMovement.kg), 0)).filter(
        GasMovement.batch_id == latest_movement.batch_id,
        GasMovement.is_initial_adjustment == False
    ).scalar() or 0
    
    kg_used = db.query(func.coalesce(func.sum(FillingOperationDetail.kg_used), 0)).filter(
        FillingOperationDetail.batch_id == latest_movement.batch_id
    ).scalar() or 0
    
    return {
        "batch_id": latest_movement.batch_id,
        "kg_sent": round(float(kg_sent), 2),
        "kg_used": round(float(kg_used), 2),
        "remaining": round(float(kg_sent) - float(kg_used), 2),
        "last_update": latest_movement.date
    }


@router.post("/gas-movements/{movement_id}/expenses")
def create_movement_expense(
    movement_id: int,
    expense: GasMovementExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    movement = db.query(GasMovement).filter(GasMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    if not movement.from_location_id:
        raise HTTPException(status_code=400, detail="Solo se pueden agregar gastos a movimientos de salida")
    
    db_expense = GasMovementExpense(
        movement_id=movement_id,
        tipo=expense.tipo,
        monto=expense.monto,
        descripcion=expense.descripcion,
        fecha=expense.fecha or datetime.now(timezone.utc)
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    
    return db_expense


@router.get("/gas-movements/{movement_id}/expenses", response_model=GasMovementExpensesSummary)
def get_movement_expenses(
    movement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    movement = db.query(GasMovement).filter(GasMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    expenses = db.query(GasMovementExpense).filter(
        GasMovementExpense.movement_id == movement_id
    ).order_by(GasMovementExpense.fecha.desc()).all()
    
    topups = db.query(ViaticosTopup).filter(
        ViaticosTopup.movement_id == movement_id
    ).order_by(ViaticosTopup.fecha.desc()).all()
    
    viaticos_inicial = movement.viaticos or 0
    viaticos_recargas = sum(t.monto for t in topups)
    viaticos_totales = viaticos_inicial + viaticos_recargas
    total_gastos = sum(e.monto for e in expenses)
    saldo = viaticos_totales - total_gastos
    
    return {
        "viaticos_inicial": viaticos_inicial,
        "viaticos_recargas": viaticos_recargas,
        "viaticos_totales": viaticos_totales,
        "expenses": expenses,
        "topups": topups,
        "total_gastos": total_gastos,
        "saldo": saldo
    }


@router.put("/gas-movements/{movement_id}/expenses")
def update_movement_expenses(
    movement_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    movement = db.query(GasMovement).filter(GasMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    # Eliminar gastos existentes y crear nuevos
    db.query(GasMovementExpense).filter(
        GasMovementExpense.movement_id == movement_id
    ).delete()
    
    expenses_data = data.get("expenses", [])
    for exp in expenses_data:
        # Aceptar ambos formatos: concepto/valor (frontend) o tipo/monto (backend)
        tipo = exp.get("concepto") or exp.get("tipo", "")
        monto = float(exp.get("valor") or exp.get("monto", 0) or 0)
        
        db_expense = GasMovementExpense(
            movement_id=movement_id,
            tipo=tipo,
            monto=monto,
            descripcion=tipo,
            fecha=datetime.now(timezone.utc)
        )
        db.add(db_expense)
    
    # Handle recargas if provided - replace all existing topups
    if "recargas" in data:
        new_recargas = float(data["recargas"])
        # Delete all existing topups for this movement
        db.query(ViaticosTopup).filter(
            ViaticosTopup.movement_id == movement_id
        ).delete()
        # Create new topup if value > 0
        if new_recargas > 0:
            new_topup = ViaticosTopup(
                movement_id=movement_id,
                monto=new_recargas,
                descripcion="Ajuste manual desde edición",
                fecha=datetime.now(timezone.utc)
            )
            db.add(new_topup)
            print(f"[GAS_OPS] Recargas actualizadas: ${new_recargas} para movimiento {movement_id}")
    
    db.commit()
    
    return {"message": "Gastos y recargas actualizados correctamente"}


@router.post("/gas-movements/{movement_id}/viaticos-topup")
def viaticos_topup(
    movement_id: int,
    topup: ViaticosTopupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    movement = db.query(GasMovement).filter(GasMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    if not movement.from_location_id:
        raise HTTPException(status_code=400, detail="Solo se pueden agregar viáticos a movimientos de salida")
    
    db_topup = ViaticosTopup(
        movement_id=movement_id,
        monto=topup.monto,
        descripcion=topup.descripcion
    )
    db.add(db_topup)
    db.commit()
    db.refresh(db_topup)
    
    return db_topup

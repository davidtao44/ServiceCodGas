from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database.database import get_db
from app.models.models import FullCylinderOutput, FullCylinderOutputDetail, TankType, User, FillingOperation, FillingOperationDetail, EmptyCylinderMovement, EmptyCylinderMovementDetail
from app.schemas.schemas import FullCylinderOutput as FullCylinderOutputSchema, FullCylinderOutputCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.post("/outputs", response_model=FullCylinderOutputSchema)
def create_full_cylinder_output(
    output: FullCylinderOutputCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not output.details:
        raise HTTPException(status_code=400, detail="Debe incluir al menos un detalle")
    
    for detail in output.details:
        tank_type = db.query(TankType).filter(TankType.id == detail.cylinder_type_id).first()
        if not tank_type:
            raise HTTPException(status_code=404, detail=f"Tipo de cilindro {detail.cylinder_type_id} no encontrado")
        
        filled_total = db.query(func.coalesce(func.sum(FillingOperationDetail.quantity), 0)).join(
            FillingOperation
        ).filter(
            FillingOperationDetail.cylinder_type_id == detail.cylinder_type_id
        ).scalar()
        
        outputs_total = db.query(func.coalesce(func.sum(FullCylinderOutputDetail.quantity), 0)).join(
            FullCylinderOutput
        ).filter(
            FullCylinderOutputDetail.cylinder_type_id == detail.cylinder_type_id
        ).scalar()
        
        available_full = filled_total - outputs_total
        
        if detail.quantity > available_full:
            raise HTTPException(
                status_code=400,
                detail=f"No hay suficientescilindros llenos para tipo {tank_type.name}. Disponibles: {available_full}, Solicitados: {detail.quantity}"
            )
    
    db_output = FullCylinderOutput(
        destination=output.destination,
        delivered_by_user_id=output.delivered_by_user_id,
        transported_by_user_id=output.transported_by_user_id,
        notes=output.notes
    )
    
    db.add(db_output)
    db.flush()
    
    for detail in output.details:
        db_detail = FullCylinderOutputDetail(
            output_id=db_output.id,
            cylinder_type_id=detail.cylinder_type_id,
            quantity=detail.quantity
        )
        db.add(db_detail)
    
    db.commit()
    db.refresh(db_output)
    
    total_qty = sum(d.quantity for d in output.details)
    types_str = ", ".join([f"{d.quantity}x tipo {d.cylinder_type_id}" for d in output.details])
    print(f"[OUTPUTS] Usuario {current_user.email} registró salida de {total_qty} cilindros llenos: {types_str} hacia {output.destination}")
    
    return db_output

@router.get("/outputs", response_model=List[FullCylinderOutputSchema])
def get_full_cylinder_outputs(
    cylinder_type_id: int = None,
    destination: str = None,
    delivered_by_user_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(FullCylinderOutput)
    
    if cylinder_type_id:
        query = query.join(FullCylinderOutput.details).filter(
            FullCylinderOutputDetail.cylinder_type_id == cylinder_type_id
        )
    if destination:
        query = query.filter(FullCylinderOutput.destination == destination)
    if delivered_by_user_id:
        query = query.filter(FullCylinderOutput.delivered_by_user_id == delivered_by_user_id)
    
    results = query.order_by(FullCylinderOutput.date.desc()).all()
    print(f"[OUTPUTS DEBUG] GET /outputs - Total salidas: {len(results)}")
    for o in results[:3]:
        print(f"[OUTPUTS DEBUG]   - ID={o.id}, destino={o.destination}, detalles={len(o.details)}")
    
    return results

@router.get("/outputs/summary")
def get_outputs_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    results = db.query(
        FullCylinderOutputDetail.cylinder_type_id,
        TankType.name,
        func.coalesce(func.sum(FullCylinderOutputDetail.quantity), 0).label("total")
    ).join(
        TankType, FullCylinderOutputDetail.cylinder_type_id == TankType.id
    ).group_by(
        FullCylinderOutputDetail.cylinder_type_id, TankType.name
    ).all()
    
    return [{"cylinder_type_id": r.cylinder_type_id, "name": r.name, "total": r.total} for r in results]

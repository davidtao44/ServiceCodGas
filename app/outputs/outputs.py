from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database.database import get_db
from app.models.models import FullCylinderOutput, TankType, User, FillingOperation, EmptyCylinderMovement
from app.schemas.schemas import FullCylinderOutput as FullCylinderOutputSchema, FullCylinderOutputCreate
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.post("/outputs", response_model=FullCylinderOutputSchema)
def create_full_cylinder_output(
    output: FullCylinderOutputCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    tank_type = db.query(TankType).filter(TankType.id == output.cylinder_type_id).first()
    if not tank_type:
        raise HTTPException(status_code=404, detail="Tipo de cilindro no encontrado")
    
    empty_received = db.query(func.coalesce(func.sum(EmptyCylinderMovement.quantity), 0)).filter(
        EmptyCylinderMovement.cylinder_type_id == output.cylinder_type_id
    ).scalar()
    
    filled_total = db.query(func.coalesce(func.sum(FillingOperation.quantity), 0)).filter(
        FillingOperation.cylinder_type_id == output.cylinder_type_id
    ).scalar()
    
    outputs_total = db.query(func.coalesce(func.sum(FullCylinderOutput.quantity), 0)).filter(
        FullCylinderOutput.cylinder_type_id == output.cylinder_type_id
    ).scalar()
    
    available_full = filled_total - outputs_total
    
    if output.quantity > available_full:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficientes cilindros llenos. Disponibles: {available_full}, Solicitados: {output.quantity}"
        )
    
    db_output = FullCylinderOutput(
        cylinder_type_id=output.cylinder_type_id,
        quantity=output.quantity,
        destination=output.destination,
        delivered_by_user_id=output.delivered_by_user_id,
        transported_by_user_id=output.transported_by_user_id,
        notes=output.notes
    )
    
    db.add(db_output)
    db.commit()
    db.refresh(db_output)
    
    print(f"[OUTPUTS] Usuario {current_user.email} registró salida de {output.quantity} cilindros llenos tipo {tank_type.name} hacia {output.destination}")
    
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
        query = query.filter(FullCylinderOutput.cylinder_type_id == cylinder_type_id)
    if destination:
        query = query.filter(FullCylinderOutput.destination == destination)
    if delivered_by_user_id:
        query = query.filter(FullCylinderOutput.delivered_by_user_id == delivered_by_user_id)
    
    return query.order_by(FullCylinderOutput.date.desc()).all()

@router.get("/outputs/summary")
def get_outputs_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    results = db.query(
        FullCylinderOutput.cylinder_type_id,
        TankType.name,
        func.coalesce(func.sum(FullCylinderOutput.quantity), 0).label("total")
    ).join(TankType).group_by(
        FullCylinderOutput.cylinder_type_id, TankType.name
    ).all()
    
    return [{"cylinder_type_id": r.cylinder_type_id, "name": r.name, "total": r.total} for r in results]

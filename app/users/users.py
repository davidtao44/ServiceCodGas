from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database.database import get_db
from app.models.models import User
from app.schemas.schemas import User as UserSchema
from app.auth.auth import get_current_active_user
from app.tank_types.tank_types import require_role

router = APIRouter()

@router.get("/users", response_model=List[UserSchema])
def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["superadmin"]))
):
    return db.query(User).offset(skip).limit(limit).all()

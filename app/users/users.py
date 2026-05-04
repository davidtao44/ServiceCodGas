from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database.database import get_db
from app.models.models import User
from app.schemas.schemas import User as UserSchema
from app.auth.auth import get_current_active_user

router = APIRouter()

@router.get("/users", response_model=List[UserSchema])
def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    print(f"[DEBUG] Usuario actual: {current_user.email}, role: {current_user.role}")
    users = db.query(User).filter(User.is_active == True).offset(skip).limit(limit).all()
    print(f"[DEBUG] Usuarios encontrados: {len(users)}")
    for u in users:
        print(f"[DEBUG] User: id={u.id}, email={u.email}, role={u.role}")
    return users

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models.models import UserRole, TankStatus, TransactionType

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole = UserRole.USER

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class GasTankTypeBase(BaseModel):
    name: str
    capacity: float
    description: Optional[str] = None

class GasTankTypeCreate(GasTankTypeBase):
    pass

class GasTankType(GasTankTypeBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class GasTankBase(BaseModel):
    type_id: int
    serial_number: str
    current_status: TankStatus = TankStatus.AVAILABLE
    location: Optional[str] = None

class GasTankCreate(GasTankBase):
    pass

class GasTankUpdate(BaseModel):
    current_status: Optional[TankStatus] = None
    location: Optional[str] = None
    last_maintenance: Optional[datetime] = None

class GasTank(GasTankBase):
    id: int
    last_maintenance: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    tank_type: GasTankType
    
    class Config:
        from_attributes = True

class InventoryBase(BaseModel):
    tank_id: int
    quantity_available: int
    minimum_stock: int = 5

class InventoryCreate(InventoryBase):
    pass

class InventoryUpdate(BaseModel):
    quantity_available: Optional[int] = None
    minimum_stock: Optional[int] = None

class Inventory(InventoryBase):
    id: int
    last_updated: datetime
    updated_by: Optional[int] = None
    tank: GasTank
    
    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    tank_id: int
    transaction_type: TransactionType
    quantity: int
    notes: Optional[str] = None

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: int
    user_id: int
    timestamp: datetime
    tank: GasTank
    user: User
    
    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    total_tanks: int
    available_tanks: int
    low_stock_items: int
    recent_transactions: List[Transaction]
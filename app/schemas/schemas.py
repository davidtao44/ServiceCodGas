from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models.models import UserRole, JornadaShift, JornadaStatus, DebtStatus

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole = UserRole.VENDEDOR

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

class TankTypeBase(BaseModel):
    name: str
    capacity: float
    price: float
    description: Optional[str] = None

class TankTypeCreate(TankTypeBase):
    pass

class TankTypeUpdate(BaseModel):
    name: Optional[str] = None
    capacity: Optional[float] = None
    price: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class TankType(TankTypeBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class InventoryLocationBase(BaseModel):
    tank_type_id: int
    location: str
    quantity: int = 0

class InventoryLocationCreate(InventoryLocationBase):
    pass

class InventoryLocationUpdate(BaseModel):
    quantity: Optional[int] = None

class InventoryLocation(InventoryLocationBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    tank_type: TankType
    
    class Config:
        from_attributes = True

class EmbasadoRequest(BaseModel):
    tank_type_id: int
    filled_quantity: int
    sent_to_sale_quantity: int

class EmbasadoResponse(BaseModel):
    tank_type_id: int
    location_planta_before: int
    location_planta_after: int
    location_venta_before: int
    location_venta_after: int
    filled_quantity: int
    sent_to_sale_quantity: int

class JornadaBase(BaseModel):
    shift: JornadaShift

class JornadaCreate(JornadaBase):
    seller_id: int

class JornadaUpdate(BaseModel):
    status: Optional[JornadaStatus] = None
    total_money: Optional[float] = None

class Jornada(JornadaBase):
    id: int
    date: datetime
    seller_id: int
    status: JornadaStatus
    total_sales: float
    total_money: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    seller: User
    
    class Config:
        from_attributes = True

class SaleBase(BaseModel):
    jornada_id: int
    tank_type_id: int
    quantity: int

class SaleCreate(SaleBase):
    pass

class Sale(SaleBase):
    id: int
    unit_price: float
    total: float
    created_at: datetime
    tank_type: TankType
    
    class Config:
        from_attributes = True

class DebtBase(BaseModel):
    jornada_id: int
    seller_id: int
    amount: float

class DebtCreate(DebtBase):
    pass

class Debt(DebtBase):
    id: int
    status: DebtStatus
    assigned_at: datetime
    paid_at: Optional[datetime] = None
    jornada: Jornada
    seller: User
    
    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    total_tank_types: int
    total_inventory_planta: int
    total_inventory_venta: int
    open_jornadas: int
    pending_debts: float
    recent_sales: List[Sale]

class CloseJornadaRequest(BaseModel):
    total_money: float

class AssignDebtRequest(BaseModel):
    seller_id: int
    amount: float

class PayDebtRequest(BaseModel):
    pass

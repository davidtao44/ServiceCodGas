from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models.models import UserRole, JornadaShift, JornadaStatus, DebtStatus, GasMovementStatus

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

class EmptyCylinderMovementDetailBase(BaseModel):
    cylinder_type_id: int
    quantity: int

class EmptyCylinderMovementDetailCreate(EmptyCylinderMovementDetailBase):
    pass

class EmptyCylinderMovementDetail(EmptyCylinderMovementDetailBase):
    id: int
    cylinder_type: TankType
    
    class Config:
        from_attributes = True

class EmptyCylinderMovementBase(BaseModel):
    source: str
    received_by_user_id: int
    delivered_by_user_id: Optional[int] = None
    notes: Optional[str] = None

class EmptyCylinderMovementCreate(EmptyCylinderMovementBase):
    details: List[EmptyCylinderMovementDetailCreate]

class EmptyCylinderMovement(EmptyCylinderMovementBase):
    id: int
    date: datetime
    details: List[EmptyCylinderMovementDetail]
    received_by: User
    delivered_by: Optional[User] = None
    
    class Config:
        from_attributes = True

class FillingOperationDetailBase(BaseModel):
    cylinder_type_id: int
    quantity: int

class FillingOperationDetailCreate(FillingOperationDetailBase):
    pass

class FillingOperationDetail(FillingOperationDetailBase):
    id: int
    kg_used: float
    cylinder_type: TankType
    
    class Config:
        from_attributes = True

class FillingOperationBase(BaseModel):
    performed_by_user_id: int
    notes: Optional[str] = None

class FillingOperationCreate(FillingOperationBase):
    details: List[FillingOperationDetailCreate]

class FillingOperation(FillingOperationBase):
    id: int
    date: datetime
    details: List[FillingOperationDetail]
    performed_by: User
    
    class Config:
        from_attributes = True

class FullCylinderOutputDetailBase(BaseModel):
    cylinder_type_id: int
    quantity: int

class FullCylinderOutputDetailCreate(FullCylinderOutputDetailBase):
    pass

class FullCylinderOutputDetail(FullCylinderOutputDetailBase):
    id: int
    cylinder_type: TankType
    
    class Config:
        from_attributes = True

class FullCylinderOutputBase(BaseModel):
    destination: str
    delivered_by_user_id: int
    transported_by_user_id: Optional[int] = None
    notes: Optional[str] = None

class FullCylinderOutputCreate(FullCylinderOutputBase):
    details: List[FullCylinderOutputDetailCreate]

class FullCylinderOutput(FullCylinderOutputBase):
    id: int
    date: datetime
    details: List[FullCylinderOutputDetail]
    delivered_by: User
    transported_by: Optional[User] = None
    
    class Config:
        from_attributes = True

class VehicleBase(BaseModel):
    name: str
    plate: Optional[str] = None
    location: str = "embasado"
    capacity_kg: Optional[float] = None

class VehicleCreate(VehicleBase):
    pass

class Vehicle(VehicleBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class DriverBase(BaseModel):
    name: str
    document: Optional[str] = None
    phone: Optional[str] = None

class DriverCreate(DriverBase):
    pass

class Driver(DriverBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class GasLoadBase(BaseModel):
    kg_loaded: float
    vehicle_plate: Optional[str] = None
    vehicle_id: Optional[int] = None
    received_by_user_id: int
    notes: Optional[str] = None

class GasLoadCreate(GasLoadBase):
    new_vehicle: Optional[VehicleCreate] = None

class GasLoad(GasLoadBase):
    id: int
    date: datetime
    received_by: User
    vehicle: Optional[Vehicle] = None
    
    class Config:
        from_attributes = True

class OperationsInventory(BaseModel):
    empty: int
    full: int
    gas: float
    empty_by_type: List[dict]
    full_by_type: List[dict]

class PaginatedResponse(BaseModel):
    data: List[dict]
    total: int
    page: int
    limit: int
    total_pages: int

class LocationBase(BaseModel):
    name: str
    max_capacity_kg: float

class LocationCreate(LocationBase):
    pass

class Location(LocationBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class LocationInventory(BaseModel):
    location_id: int
    location_name: str
    stock_kg: float
    max_capacity_kg: float
    utilization_percentage: float

class GasMovementBase(BaseModel):
    from_location_id: Optional[int] = None
    to_location_id: Optional[int] = None
    from_custom: Optional[str] = None
    to_custom: Optional[str] = None
    batch_id: Optional[str] = None
    vehicle_id: Optional[int] = None
    driver_id: Optional[int] = None
    kg: float
    notes: Optional[str] = None

class GasMovementCreate(GasMovementBase):
    new_driver: Optional[DriverCreate] = None
    viaticos: Optional[float] = None

class GasMovementReceive(BaseModel):
    kg_arrived: float
    notes: Optional[str] = None
    received_by_user_id: Optional[int] = None

class GasMovement(GasMovementBase):
    id: int
    date: datetime
    kg_arrived: Optional[float] = None
    status: GasMovementStatus
    created_by: int
    related_movement_id: Optional[int] = None
    is_initial_adjustment: bool = False
    from_location: Optional[Location] = None
    to_location: Optional[Location] = None
    
    class Config:
        from_attributes = True

class GasMovementWithDifference(GasMovement):
    difference: Optional[float] = None


class GasMovementExpenseCreate(BaseModel):
    tipo: str
    monto: float
    descripcion: Optional[str] = None
    fecha: Optional[datetime] = None


class GasMovementExpenseResponse(BaseModel):
    id: int
    tipo: str
    monto: float
    descripcion: Optional[str] = None
    fecha: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


class ViaticosTopupCreate(BaseModel):
    monto: float
    descripcion: Optional[str] = None


class ViaticosTopupResponse(BaseModel):
    id: int
    movement_id: int
    monto: float
    fecha: datetime
    descripcion: Optional[str] = None
    
    class Config:
        from_attributes = True


class GasMovementExpensesSummary(BaseModel):
    viaticos_inicial: Optional[float] = None
    viaticos_recargas: float = 0
    viaticos_totales: float = 0
    expenses: List[GasMovementExpenseResponse]
    topups: List[ViaticosTopupResponse] = []
    total_gastos: float
    saldo: float

class EmbasadoFixResponse(BaseModel):
    total_consumed_kg: float
    adjustment_created: bool
    adjustment_id: Optional[int] = None
    new_stock: float
    message: str

class BatchRendimiento(BaseModel):
    batch_id: str
    kg_enviados: float
    kg_usados: float
    diferencia: float
    cilindros_extra: int
    fecha_primer_movimiento: datetime
    fecha_ultimo_movimiento: datetime
    movimientos: int
    
    class Config:
        from_attributes = True

class FlexibleFillingRequest(BaseModel):
    tank_type_id: int
    filled_quantity: int
    notes: Optional[str] = None
    force_continue: bool = False

class FlexibleFillingResponse(BaseModel):
    success: bool
    message: str
    cylinders_filled: int
    kg_used: float
    remaining_stock: float
    batch_id: Optional[str] = None

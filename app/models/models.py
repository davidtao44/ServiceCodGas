from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database.database import Base
import enum

class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    EMBASADOR = "embasador"
    VENDEDOR = "vendedor"

class JornadaShift(str, enum.Enum):
    MANANA = "mañana"
    TARDE = "tarde"
    NOCHE = "noche"

class JornadaStatus(str, enum.Enum):
    ABIERTA = "abierta"
    CERRADA = "cerrada"

class DebtStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    PAGADA = "pagada"

class CylinderMovementSource(str, enum.Enum):
    CLIENTES = "clientes"
    PLANTA = "planta"
    OTRO = "otro"

class CylinderOutputDestination(str, enum.Enum):
    VENTA = "venta"
    CLIENTES = "clientes"
    PLANTA = "planta"
    OTRO = "otro"

class GasMovementStatus(str, enum.Enum):
    EN_TRANSITO = "en_transito"
    COMPLETADO = "completado"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.VENDEDOR, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    jornadas = relationship("Jornada", back_populates="seller")
    debts = relationship("Debt", back_populates="seller")

class TankType(Base):
    __tablename__ = "tank_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    capacity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    description = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    inventory_locations = relationship("InventoryLocation", back_populates="tank_type")
    sales = relationship("Sale", back_populates="tank_type")

class InventoryLocation(Base):
    __tablename__ = "inventory_locations"
    
    id = Column(Integer, primary_key=True, index=True)
    tank_type_id = Column(Integer, ForeignKey("tank_types.id"), nullable=False)
    location = Column(String, nullable=False)
    quantity = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    tank_type = relationship("TankType", back_populates="inventory_locations")

class Jornada(Base):
    __tablename__ = "jornadas"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), server_default=func.now())
    shift = Column(Enum(JornadaShift), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(JornadaStatus), default=JornadaStatus.ABIERTA, nullable=False)
    total_sales = Column(Float, default=0.0)
    total_money = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    seller = relationship("User", back_populates="jornadas")
    sales = relationship("Sale", back_populates="jornada")
    debts = relationship("Debt", back_populates="jornada")

class Sale(Base):
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    jornada_id = Column(Integer, ForeignKey("jornadas.id"), nullable=False)
    tank_type_id = Column(Integer, ForeignKey("tank_types.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    jornada = relationship("Jornada", back_populates="sales")
    tank_type = relationship("TankType", back_populates="sales")

class Debt(Base):
    __tablename__ = "debts"
    
    id = Column(Integer, primary_key=True, index=True)
    jornada_id = Column(Integer, ForeignKey("jornadas.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum(DebtStatus), default=DebtStatus.PENDIENTE, nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    jornada = relationship("Jornada", back_populates="debts")
    seller = relationship("User", back_populates="debts")

class EmptyCylinderMovement(Base):
    __tablename__ = "empty_cylinder_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    received_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    delivered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    date = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)
    
    received_by = relationship("User", foreign_keys=[received_by_user_id])
    delivered_by = relationship("User", foreign_keys=[delivered_by_user_id])
    details = relationship("EmptyCylinderMovementDetail", back_populates="movement", cascade="all, delete-orphan")

class EmptyCylinderMovementDetail(Base):
    __tablename__ = "empty_cylinder_movement_details"
    
    id = Column(Integer, primary_key=True, index=True)
    movement_id = Column(Integer, ForeignKey("empty_cylinder_movements.id"), nullable=False)
    cylinder_type_id = Column(Integer, ForeignKey("tank_types.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    
    movement = relationship("EmptyCylinderMovement", back_populates="details")
    cylinder_type = relationship("TankType")

class FillingOperation(Base):
    __tablename__ = "filling_operations"
    
    id = Column(Integer, primary_key=True, index=True)
    performed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)
    
    performed_by = relationship("User")
    details = relationship("FillingOperationDetail", back_populates="operation", cascade="all, delete-orphan")

class FillingOperationDetail(Base):
    __tablename__ = "filling_operation_details"
    
    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(Integer, ForeignKey("filling_operations.id"), nullable=False)
    cylinder_type_id = Column(Integer, ForeignKey("tank_types.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    kg_used = Column(Float, nullable=False)
    
    operation = relationship("FillingOperation", back_populates="details")
    cylinder_type = relationship("TankType")

class FullCylinderOutput(Base):
    __tablename__ = "full_cylinder_outputs"
    
    id = Column(Integer, primary_key=True, index=True)
    destination = Column(String, nullable=False)
    delivered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transported_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    date = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)
    
    delivered_by = relationship("User", foreign_keys=[delivered_by_user_id])
    transported_by = relationship("User", foreign_keys=[transported_by_user_id])
    details = relationship("FullCylinderOutputDetail", back_populates="output", cascade="all, delete-orphan")

class FullCylinderOutputDetail(Base):
    __tablename__ = "full_cylinder_output_details"
    
    id = Column(Integer, primary_key=True, index=True)
    output_id = Column(Integer, ForeignKey("full_cylinder_outputs.id"), nullable=False)
    cylinder_type_id = Column(Integer, ForeignKey("tank_types.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    
    output = relationship("FullCylinderOutput", back_populates="details")
    cylinder_type = relationship("TankType")

class GasLoad(Base):
    __tablename__ = "gas_loads"
    
    id = Column(Integer, primary_key=True, index=True)
    kg_loaded = Column(Float, nullable=False)
    vehicle_plate = Column(String, nullable=True)
    received_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)
    
    received_by = relationship("User")

class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    max_capacity_kg = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    movements_from = relationship("GasMovement", foreign_keys="GasMovement.from_location_id", back_populates="from_location")
    movements_to = relationship("GasMovement", foreign_keys="GasMovement.to_location_id", back_populates="to_location")

class GasMovement(Base):
    __tablename__ = "gas_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), server_default=func.now())
    from_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    to_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    kg = Column(Float, nullable=False)
    kg_arrived = Column(Float, nullable=True)
    status = Column(Enum(GasMovementStatus), default=GasMovementStatus.EN_TRANSITO, nullable=False)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    related_movement_id = Column(Integer, ForeignKey("gas_movements.id"), nullable=True)
    is_initial_adjustment = Column(Boolean, default=False, nullable=False)
    
    from_location = relationship("Location", foreign_keys=[from_location_id], back_populates="movements_from")
    to_location = relationship("Location", foreign_keys=[to_location_id], back_populates="movements_to")
    creator = relationship("User")
    related_movement = relationship("GasMovement", remote_side=[id])

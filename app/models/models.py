from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, ForeignKey, Float
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

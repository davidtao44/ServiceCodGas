from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database.database import Base
import enum

class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"

class TankStatus(str, enum.Enum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"

class TransactionType(str, enum.Enum):
    IN = "in"
    OUT = "out"
    TRANSFER = "transfer"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    transactions = relationship("Transaction", back_populates="user")

class GasTankType(Base):
    __tablename__ = "gas_tank_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    capacity = Column(Float, nullable=False)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    tanks = relationship("GasTank", back_populates="tank_type")

class GasTank(Base):
    __tablename__ = "gas_tanks"
    
    id = Column(Integer, primary_key=True, index=True)
    type_id = Column(Integer, ForeignKey("gas_tank_types.id"), nullable=False)
    serial_number = Column(String, unique=True, index=True, nullable=False)
    current_status = Column(Enum(TankStatus), default=TankStatus.AVAILABLE, nullable=False)
    location = Column(String)
    last_maintenance = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    tank_type = relationship("GasTankType", back_populates="tanks")
    inventory = relationship("Inventory", back_populates="tank", uselist=False)
    transactions = relationship("Transaction", back_populates="tank")

class Inventory(Base):
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    tank_id = Column(Integer, ForeignKey("gas_tanks.id"), unique=True, nullable=False)
    quantity_available = Column(Integer, default=0, nullable=False)
    minimum_stock = Column(Integer, default=5, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    tank = relationship("GasTank", back_populates="inventory")
    updater = relationship("User")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    tank_id = Column(Integer, ForeignKey("gas_tanks.id"), nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    quantity = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(String)
    
    tank = relationship("GasTank", back_populates="transactions")
    user = relationship("User", back_populates="transactions")
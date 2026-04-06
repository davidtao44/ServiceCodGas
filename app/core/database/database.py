from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config.settings import settings

def create_engine_with_pool():
    """Crea el engine con configuración óptima para producción."""
    
    # Configuración del pool para producción
    engine = create_engine(
        settings.database_url,
        # Pool de conexiones
        pool_size=10,           # Conexiones mantenidas
        max_overflow=20,        # Conexiones adicionales bajo demanda
        pool_timeout=30,        # Timeout al obtener conexión
        pool_recycle=1800,      # Reciclar conexiones cada 30 min
        pool_pre_ping=True,     # Verificar conexión antes de usar
        # Timeouts de conexión
        connect_args={
            "connect_timeout": 10,
            "application_name": "codgas-api",
            "keepalives": 1,
            "keepalives_idle": 30,
        },
        echo=False,             # True solo para debug
    )
    
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Event listener para nuevas conexiones."""
        # Configurar keepalives
        if hasattr(dbapi_conn, 'set_session'):
            pass  # No autocommit here, let SQLAlchemy handle it
    
    return engine

engine = create_engine_with_pool()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    """
    Generador de sesiones de base de datos.
    
    Uso en FastAPI:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
    
    El uso de 'yield' con 'finally' asegura que la sesión
    siempre se cierre, incluso si hay errores.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        # Rollback en caso de error
        db.rollback()
        raise e
    finally:
        db.close()


def get_db_session():
    """
    Alternativa síncrona para uso fuera de FastAPI.
    Debe cerrarse manualmente.
    """
    return SessionLocal()


def init_db():
    """Inicializa la base de datos - crear tablas si no existen."""
    Base.metadata.create_all(bind=engine)


def check_connection():
    """Verifica la conexión a la base de datos."""
    try:
        with engine.connect() as conn:
            return True
    except Exception as e:
        print(f"Error de conexión: {e}")
        return False

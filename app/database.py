import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Index, func, DECIMAL, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# === KONFIGURASI KONEKSI MYSQL ===
DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    f"?charset=utf8mb4"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    future=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
db_session = scoped_session(SessionLocal)
Base = declarative_base()

# === MODEL ===
class Gempa(Base):
    __tablename__ = "gempa"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_key = Column(String(255), nullable=False, index=True)
    kategori = Column(String(50), nullable=False, index=True, default="csv")
    tanggal = Column(String(100))
    jam = Column(String(20))
    datetime = Column(DateTime, index=True)
    event_year = Column(Integer, index=True)
    event_month = Column(Integer, index=True)
    magnitude = Column(DECIMAL(4, 2), index=True)
    kedalaman = Column(Float)
    latitude = Column(DECIMAL(10, 6), index=True)
    longitude = Column(DECIMAL(10, 6), index=True)
    wilayah = Column(String(255), index=True)
    lokasi_detail = Column(Text)
    ai_status = Column(String(100))
    ai_rekomendasi = Column(Text)
    source = Column(String(100), default="csv")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_unique", "event_key", "kategori", unique=True),
        Index("idx_loc", "latitude", "longitude"),
    )

# === FUNGSI ===
def get_db():
    """Dependency untuk FastAPI endpoint"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize MySQL database"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("✅ Koneksi ke MySQL berhasil!")
        Base.metadata.create_all(bind=engine)
        logger.info(f"✅ Tabel 'gempa' siap di database '{settings.DB_NAME}'")
    except Exception as e:
        logger.error(f"❌ Gagal koneksi ke MySQL: {e}")
        raise

def query_chart_data(db_session, tahun: int, kategori: str = None):
    """Get aggregated monthly data for charts"""
    query = db_session.query(
        Gempa.event_month,
        func.count(Gempa.id),
        func.avg(Gempa.magnitude),
        func.max(Gempa.magnitude)
    ).filter(Gempa.event_year == tahun)
    
    if kategori and kategori != "semua":
        query = query.filter(Gempa.kategori == kategori)
    
    rows = query.group_by(Gempa.event_month).all()
    
    # Fill all 12 months
    months = {i: [0, 0.0, 0.0] for i in range(1, 13)}
    for row in rows:
        if row[0] and 1 <= row[0] <= 12:
            months[row[0]] = [row[1], float(row[2] or 0), float(row[3] or 0)]
    
    labels = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"]
    return {
        "labels": labels,
        "jumlah": [months[i][0] for i in range(1, 13)],
        "avg_magnitude": [months[i][1] for i in range(1, 13)],
        "max_magnitude": [months[i][2] for i in range(1, 13)]
    }

def query_history(db_session, tahun: int, kategori: str = None, limit: int = 50, offset: int = 0):
    """Get paginated historical data"""
    query = db_session.query(Gempa).filter(Gempa.event_year == tahun)
    
    if kategori and kategori != "semua":
        query = query.filter(Gempa.kategori == kategori)
    
    total = query.count()
    items = query.order_by(Gempa.datetime.desc()).offset(offset).limit(limit).all()
    
    return items, total

def get_available_years(db_session):
    """Get list of years with data"""
    result = db_session.query(Gempa.event_year).filter(
        Gempa.event_year.isnot(None)
    ).distinct().order_by(Gempa.event_year.desc()).all()
    return [row[0] for row in result if row[0]]
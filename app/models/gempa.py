from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime

class GempaItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    event_key: str
    kategori: str = "kaggle"
    tanggal: Optional[str] = None
    jam: Optional[str] = None
    datetime: Optional[datetime] = None
    event_year: Optional[int] = None
    event_month: Optional[int] = None
    magnitude: Optional[float] = Field(None, ge=0, le=10)
    kedalaman: Optional[float] = Field(None, ge=0)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    wilayah: str
    lokasi_detail: Optional[str] = None
    ai_status: Optional[str] = None
    ai_rekomendasi: Optional[str] = None
    source: Optional[str] = "kaggle"
    created_at: Optional[datetime] = None

class ApiResponse(BaseModel):
    source: str = "API"
    total: Optional[int] = None
    data: Optional[GempaItem | List[GempaItem]] = None
    message: Optional[str] = None

class ChartResponse(BaseModel):
    tahun: int
    kategori: str
    labels: List[str]
    jumlah: List[int]
    avg_magnitude: List[float]
    max_magnitude: List[float]

class ImportResponse(BaseModel):
    status: str
    message: str
    total_imported: int
    total_in_db: Optional[int] = None
# app/routers/api.py
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.database import get_db, Gempa, query_chart_data

router = APIRouter(prefix="/api", tags=["API"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    return {"status": "healthy", "database": "mysql", "version": "2.0.0"}

@router.get("/years")
async def get_available_years(db: Session = Depends(get_db)):
    """Get list of years that have data"""
    try:
        result = db.query(Gempa.event_year).filter(
            Gempa.event_year.isnot(None)
        ).distinct().order_by(Gempa.event_year.desc()).all()
        years = [row[0] for row in result if row[0]]
        return {"years": years}
    except Exception as e:
        logger.error(f"Error fetching years: {e}")
        return {"years": []}

@router.get("/stats/summary")
async def get_summary(db: Session = Depends(get_db)):
    try:
        total = db.query(Gempa).count()
        
        latest_year_row = db.query(Gempa.event_year).filter(
            Gempa.event_year.isnot(None)
        ).distinct().order_by(Gempa.event_year.desc()).first()
        latest_year = latest_year_row[0] if latest_year_row else 2024
        
        max_mag_row = db.query(Gempa.magnitude).filter(
            Gempa.magnitude.isnot(None)
        ).order_by(Gempa.magnitude.desc()).first()
        max_magnitude = float(max_mag_row[0]) if max_mag_row else 0.0
        
        year_count = db.query(Gempa).filter(Gempa.event_year == latest_year).count()
        
        return {
            "total_records": total,
            "latest_year": latest_year,
            "max_magnitude": round(max_magnitude, 1),
            "records_this_year": year_count
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"total_records": 0, "latest_year": 2024, "max_magnitude": 0.0, "records_this_year": 0}

@router.get("/gempa-terbaru")
async def get_latest(db: Session = Depends(get_db)):
    latest = db.query(Gempa).filter(
        Gempa.datetime.isnot(None)
    ).order_by(Gempa.datetime.desc()).first()
    
    if not latest:
        return {"data": None, "message": "Belum ada data gempa"}
    
    # Convert to dict safely
    data = {
        "id": latest.id,
        "event_key": latest.event_key,
        "tanggal": str(latest.tanggal) if latest.tanggal else None,
        "jam": str(latest.jam) if latest.jam else None,
        "datetime": latest.datetime.isoformat() if latest.datetime else None,
        "magnitude": float(latest.magnitude) if latest.magnitude else 0.0,
        "kedalaman": float(latest.kedalaman) if latest.kedalaman else 0.0,
        "latitude": float(latest.latitude) if latest.latitude else 0.0,
        "longitude": float(latest.longitude) if latest.longitude else 0.0,
        "wilayah": latest.wilayah or "Unknown",
        "ai_status": latest.ai_status or "🟢 RELATIF AMAN",
        "ai_rekomendasi": latest.ai_rekomendasi or "-"
    }
    return {"data": data, "source": "database"}

@router.get("/gempa-history")
async def get_history(
    db: Session = Depends(get_db),
    tahun: int = Query(None, description="Filter by year"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    query = db.query(Gempa)
    if tahun:
        query = query.filter(Gempa.event_year == tahun)
        
    total = query.count()
    items = query.order_by(Gempa.datetime.desc()).offset(offset).limit(limit).all()
    
    data = []
    for item in items:
        data.append({
            "id": item.id,
            "event_key": item.event_key,
            "tanggal": str(item.tanggal) if item.tanggal else None,
            "jam": str(item.jam) if item.jam else None,
            "datetime": item.datetime.isoformat() if item.datetime else None,
            "event_year": item.event_year,
            "magnitude": float(item.magnitude) if item.magnitude else 0.0,
            "kedalaman": float(item.kedalaman) if item.kedalaman else 0.0,
            "latitude": float(item.latitude) if item.latitude else 0.0,
            "longitude": float(item.longitude) if item.longitude else 0.0,
            "wilayah": item.wilayah or "Unknown",
            "ai_status": item.ai_status or "🟢 RELATIF AMAN"
        })
        
    return {
        "tahun": tahun,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data
    }

@router.get("/grafik-tahunan")
async def get_chart(db: Session = Depends(get_db), tahun: int = Query(None)):
    # Auto-select latest year if not provided
    if not tahun:
        latest = db.query(Gempa.event_year).filter(
            Gempa.event_year.isnot(None)
        ).order_by(Gempa.event_year.desc()).first()
        tahun = latest[0] if latest else 2024
        
    chart_data = query_chart_data(db, tahun)
    return {"tahun": tahun, **chart_data}
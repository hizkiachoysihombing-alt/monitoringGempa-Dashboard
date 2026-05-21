# app/services/data_loader.py
import os
import logging
import pandas as pd
from typing import Dict, Any
from sqlalchemy import text
from app.database import engine, Gempa
from app.services.ai_analyzer import analyze_risk
from app.utils.helpers import generate_event_key

logger = logging.getLogger(__name__)

def import_from_file(file_path: str) -> Dict[str, Any]:
    """Import dari satu file CSV/TSV"""
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}
    
    logger.info(f"📂 Reading: {os.path.basename(file_path)}")
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == '.csv':
            df = pd.read_csv(file_path, encoding='utf-8', low_memory=False)
        elif ext == '.tsv':
            df = pd.read_csv(file_path, sep='\t', encoding='utf-8', low_memory=False)
        else:
            return {"status": "skip", "message": f"Unsupported: {ext}"}
        
        logger.info(f"  ✅ Loaded {len(df)} rows")
    except Exception as e:
        return {"status": "error", "message": f"Read failed: {str(e)}"}
    
    # Normalisasi kolom
    col_map = {}
    for target, variants in {
        'tanggal': ['Tanggal', 'Date', 'Time', 'Waktu'],
        'magnitude': ['Magnitude', 'Mag', 'M', 'magnitude'],
        'kedalaman': ['Depth', 'Kedalaman', 'depth'],
        'latitude': ['Latitude', 'Lintang', 'lat', 'Latitude'],
        'longitude': ['Longitude', 'Bujur', 'lon', 'Longitude'],
        'wilayah': ['Wilayah', 'Lokasi', 'Location', 'Region'],
    }.items():
        for v in variants:
            if v in df.columns:
                col_map[v] = target
                break
    
    if col_map:
        df = df.rename(columns=col_map)
    
    # Konversi tipe
    df['magnitude'] = pd.to_numeric(df.get('magnitude', 0), errors='coerce')
    df['kedalaman'] = pd.to_numeric(df.get('kedalaman', 0), errors='coerce')
    df['latitude'] = pd.to_numeric(df.get('latitude', 0), errors='coerce')
    df['longitude'] = pd.to_numeric(df.get('longitude', 0), errors='coerce')
    
    # Parse datetime
    if 'tanggal' in df.columns:
        df['datetime'] = pd.to_datetime(df['tanggal'], errors='coerce')
        df['event_year'] = df['datetime'].dt.year
        df['event_month'] = df['datetime'].dt.month
    else:
        df['datetime'] = pd.NaT
        df['event_year'] = None
        df['event_month'] = None
    
    if 'wilayah' not in df.columns:
        df['wilayah'] = 'Unknown'
    df['wilayah'] = df['wilayah'].fillna('Unknown')
    
    # AI Analysis
    df['ai_status'] = df.apply(
        lambda r: analyze_risk(r['magnitude'], r['kedalaman'])[0], axis=1
    )
    df['ai_rekomendasi'] = df.apply(
        lambda r: analyze_risk(r['magnitude'], r['kedalaman'])[1], axis=1
    )
    
    # Generate key
    df['event_key'] = df.apply(
        lambda r: generate_event_key({
            'datetime': str(r['datetime']),
            'magnitude': r['magnitude'],
            'latitude': r['latitude'],
            'longitude': r['longitude']
        }), axis=1
    )
    
    df['kategori'] = 'csv'
    df = df.fillna('')
    
    # Save to DB
    save_cols = ['event_key','kategori','tanggal','datetime','event_year','event_month',
                 'magnitude','kedalaman','latitude','longitude','wilayah',
                 'ai_status','ai_rekomendasi']
    available = [c for c in save_cols if c in df.columns]
    df_db = df[available].copy()
    
    try:
        with engine.begin() as conn:
            count_before = conn.execute(text("SELECT COUNT(*) FROM gempa")).scalar()
            df_db.to_sql('gempa', con=conn, if_exists='append', index=False, method='multi', chunksize=500)
            count_after = conn.execute(text("SELECT COUNT(*) FROM gempa")).scalar()
            
            inserted = count_after - count_before
            logger.info(f"  ✅ Imported {inserted} records")
            
            return {
                "status": "success",
                "imported": int(inserted),
                "total": int(count_after)
            }
    except Exception as e:
        logger.error(f"  ❌ DB error: {e}")
        return {"status": "error", "message": str(e)}

def import_all_data_files(data_dir: str, force: bool = False) -> Dict[str, Any]:
    """Import semua file CSV/TSV di folder"""
    logger.info(f"📁 Scanning: {data_dir}")
    
    if not os.path.exists(data_dir):
        return {"status": "error", "message": "Data directory not found"}
    
    total_imported = 0
    total_in_db = 0
    files_processed = 0
    
    # Clear jika force
    if force:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM gempa"))
            logger.info("🧹 Cleared database")
    
    # Process files
    for filename in os.listdir(data_dir):
        if filename.endswith(('.csv', '.tsv')) and not filename.startswith('.'):
            file_path = os.path.join(data_dir, filename)
            result = import_from_file(file_path)
            
            if result.get("status") == "success":
                total_imported += result.get("imported", 0)
                total_in_db = result.get("total", 0)
                files_processed += 1
    
    if files_processed > 0:
        return {
            "status": "success",
            "message": f"Imported {total_imported} records from {files_processed} files",
            "total_imported": total_imported,
            "total_in_db": total_in_db
        }
    else:
        return {"status": "warning", "message": "No CSV/TSV files found"}
# app/services/data_loader.py

import os
import re
import hashlib
import logging
from typing import Dict, Any, Optional, List

import pandas as pd
import numpy as np
from sqlalchemy import text

from app.database import engine
from app.services.ai_analyzer import analyze_risk

logger = logging.getLogger(__name__)


# =========================================================
# HELPER
# =========================================================

def normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).strip().lower())


def find_column(df: pd.DataFrame, variants: List[str]) -> Optional[str]:
    normalized_columns = {
        normalize_column_name(col): col
        for col in df.columns
    }

    normalized_variants = [normalize_column_name(v) for v in variants]

    # Exact match
    for variant in normalized_variants:
        if variant in normalized_columns:
            return normalized_columns[variant]

    # Contains match, tapi jangan untuk variasi sangat pendek seperti "m" atau "x"
    for col_norm, original_col in normalized_columns.items():
        for variant in normalized_variants:
            if len(variant) >= 3 and variant in col_norm:
                return original_col

    return None


def clean_text(value, default: str = "Unknown") -> str:
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    value = str(value).strip()

    if value == "" or value.lower() in ["nan", "none", "nat", "null"]:
        return default

    return value


def extract_number(value) -> Optional[float]:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    value = str(value).strip().replace(",", ".")

    if value == "" or value.lower() in ["nan", "none", "nat", "null"]:
        return None

    match = re.search(r"-?\d+(\.\d+)?", value)

    if not match:
        return None

    try:
        return float(match.group(0))
    except Exception:
        return None


def parse_latitude(value) -> Optional[float]:
    number = extract_number(value)

    if number is None:
        return None

    text_value = str(value).upper()

    if "LS" in text_value or text_value.endswith("S"):
        return -abs(number)

    return number


def parse_longitude(value) -> Optional[float]:
    number = extract_number(value)

    if number is None:
        return None

    text_value = str(value).upper()

    if "BB" in text_value or text_value.endswith("W"):
        return -abs(number)

    return number


def make_event_key(row: dict) -> str:
    raw = (
        f"{row.get('datetime')}|"
        f"{row.get('magnitude')}|"
        f"{row.get('kedalaman')}|"
        f"{row.get('latitude')}|"
        f"{row.get('longitude')}|"
        f"{row.get('wilayah')}"
    )

    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# =========================================================
# READ FILE
# =========================================================

def read_dataset_file(file_path: str) -> pd.DataFrame:
    ext = os.path.splitext(file_path)[1].lower()
    encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]

    last_error = None

    for encoding in encodings:
        try:
            if ext == ".csv":
                try:
                    df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        low_memory=False
                    )

                    if len(df.columns) == 1:
                        df = pd.read_csv(
                            file_path,
                            encoding=encoding,
                            sep=";",
                            low_memory=False
                        )

                    return df

                except Exception:
                    # Jangan pakai low_memory saat engine="python"
                    df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        sep=None,
                        engine="python"
                    )

                    return df

            if ext == ".tsv":
                return pd.read_csv(
                    file_path,
                    sep="\t",
                    encoding=encoding,
                    low_memory=False
                )

            raise ValueError(f"Format file tidak didukung: {ext}")

        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Gagal membaca file {file_path}: {last_error}")


# =========================================================
# DATETIME
# =========================================================

def parse_datetime(df: pd.DataFrame) -> pd.Series:
    date_col = find_column(df, [
        "tanggal",
        "tgl",
        "date",
        "datetime",
        "date_time",
        "event_date",
        "event_time",
        "origin_date",
        "origin_time",
        "time",
        "waktu",
        "waktu_gempa"
    ])

    time_col = find_column(df, [
        "jam",
        "ot",
        "hour",
        "time_only",
        "origin_time",
        "waktu_jam"
    ])

    if date_col and time_col and date_col != time_col:
        raw = (
            df[date_col].fillna("").astype(str).str.strip()
            + " "
            + df[time_col].fillna("").astype(str).str.strip()
        )
    elif date_col:
        raw = df[date_col].fillna("").astype(str).str.strip()
    else:
        return pd.Series(pd.NaT, index=df.index)

    dt = pd.to_datetime(raw, errors="coerce")

    # Coba dayfirst jika parsing awal gagal banyak
    if dt.notna().sum() < max(1, int(len(df) * 0.2)):
        dt_dayfirst = pd.to_datetime(raw, errors="coerce", dayfirst=True)

        if dt_dayfirst.notna().sum() > dt.notna().sum():
            dt = dt_dayfirst

    return dt


# =========================================================
# PREPARE DATA
# =========================================================

def prepare_dataframe(df: pd.DataFrame, source_name: str = "dataset") -> pd.DataFrame:
    logger.info(f"Original columns: {list(df.columns)}")

    date_col = find_column(df, [
        "tanggal",
        "tgl",
        "date",
        "datetime",
        "date_time",
        "event_date",
        "event_time",
        "origin_date",
        "origin_time",
        "time",
        "waktu",
        "waktu_gempa"
    ])

    time_col = find_column(df, [
        "jam",
        "ot",
        "hour",
        "time_only",
        "origin_time",
        "waktu_jam"
    ])

    mag_col = find_column(df, [
        "magnitude",
        "magnitudo",
        "mag",
        "magnitude_mw",
        "magnitudo_m",
        "earthquake_magnitude",
        "richter",
        "mw",
        "mb",
        "ml",
        "m"
    ])

    depth_col = find_column(df, [
        "kedalaman",
        "kedalaman_km",
        "depth",
        "depth_km",
        "focal_depth",
        "hypocenter_depth",
        "depth_in_km"
    ])

    lat_col = find_column(df, [
        "latitude",
        "lat",
        "lintang",
        "lintang_ls",
        "y"
    ])

    lon_col = find_column(df, [
        "longitude",
        "lon",
        "lng",
        "bujur",
        "bujur_bt",
        "x"
    ])

    wilayah_col = find_column(df, [
        "wilayah",
        "lokasi",
        "location",
        "region",
        "place",
        "area",
        "remark",
        "remarks",
        "wilayah_gempa",
        "location_name"
    ])

    tsunami_col = find_column(df, [
        "tsunami_probability",
        "tsunami_prob",
        "probability_tsunami",
        "tsunami",
        "potensi_tsunami",
        "tsunami_potential"
    ])

    logger.info(
        "Column mapping: "
        f"date={date_col}, time={time_col}, mag={mag_col}, depth={depth_col}, "
        f"lat={lat_col}, lon={lon_col}, wilayah={wilayah_col}, tsunami={tsunami_col}"
    )

    out = pd.DataFrame(index=df.index)

    out["datetime"] = parse_datetime(df)

    if date_col:
        out["tanggal"] = df[date_col].fillna("").astype(str)
    else:
        out["tanggal"] = out["datetime"].dt.strftime("%Y-%m-%d")

    if time_col:
        out["jam"] = df[time_col].fillna("").astype(str)
    else:
        out["jam"] = out["datetime"].dt.strftime("%H:%M:%S")

    out["event_year"] = out["datetime"].dt.year
    out["event_month"] = out["datetime"].dt.month

    out["magnitude"] = df[mag_col].apply(extract_number) if mag_col else None
    out["kedalaman"] = df[depth_col].apply(extract_number) if depth_col else None
    out["latitude"] = df[lat_col].apply(parse_latitude) if lat_col else None
    out["longitude"] = df[lon_col].apply(parse_longitude) if lon_col else None

    if wilayah_col:
        out["wilayah"] = df[wilayah_col].apply(lambda x: clean_text(x, "Unknown"))
    else:
        out["wilayah"] = "Unknown"

    if tsunami_col:
        out["tsunami_probability"] = df[tsunami_col].apply(extract_number)
    else:
        out["tsunami_probability"] = 0.0

    for col in [
        "event_year",
        "event_month",
        "magnitude",
        "kedalaman",
        "latitude",
        "longitude",
        "tsunami_probability"
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    before = len(out)

    # Buang baris yang tidak punya tahun karena dashboard butuh event_year
    out = out[out["event_year"].notna()].copy()
    after_date = len(out)

    # Buang baris yang tidak punya koordinat karena peta butuh latitude-longitude
    out = out[out["latitude"].notna() & out["longitude"].notna()].copy()
    after_coord = len(out)

    # Isi default aman
    out["magnitude"] = out["magnitude"].fillna(0.0)
    out["kedalaman"] = out["kedalaman"].fillna(10.0)
    out["tsunami_probability"] = out["tsunami_probability"].fillna(0.0)

    out["event_year"] = out["event_year"].astype(int)
    out["event_month"] = out["event_month"].astype(int)

    def run_risk(row):
        try:
            return analyze_risk(
                row["magnitude"],
                row["kedalaman"],
                row.get("tsunami_probability", 0.0)
            )
        except TypeError:
            return analyze_risk(row["magnitude"], row["kedalaman"])
        except Exception:
            return "🟢 RELATIF AMAN", "Risiko rendah."

    risks = out.apply(run_risk, axis=1)
    out["ai_status"] = risks.apply(lambda x: x[0])
    out["ai_rekomendasi"] = risks.apply(lambda x: x[1])

    out["kategori"] = "csv"
    out["source"] = source_name
    out["event_key"] = out.apply(lambda r: make_event_key(r.to_dict()), axis=1)

    logger.info(
        f"Rows before={before}, after_date={after_date}, after_coord={after_coord}, final={len(out)}"
    )

    return out


# =========================================================
# DATABASE
# =========================================================

def get_db_columns(conn) -> List[str]:
    rows = conn.execute(text("SHOW COLUMNS FROM gempa")).fetchall()
    return [row[0] for row in rows]


def sanitize_records(records: List[dict]) -> List[dict]:
    clean_records = []

    for record in records:
        clean_record = {}

        for key, value in record.items():
            if value is None:
                clean_record[key] = None
                continue

            try:
                if pd.isna(value):
                    clean_record[key] = None
                    continue
            except Exception:
                pass

            if isinstance(value, (np.integer,)):
                clean_record[key] = int(value)
            elif isinstance(value, (np.floating,)):
                clean_record[key] = float(value)
            elif isinstance(value, pd.Timestamp):
                clean_record[key] = value.to_pydatetime()
            elif str(value).strip().lower() in ["", "nan", "none", "nat", "null"]:
                clean_record[key] = None
            else:
                clean_record[key] = value

        clean_records.append(clean_record)

    return clean_records


def clean_for_database(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df["datetime"] = df["datetime"].apply(
            lambda x: x.to_pydatetime() if pd.notna(x) else None
        )

    for col in ["event_year", "event_month"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].apply(lambda x: int(x) if pd.notna(x) else None)

    for col in [
        "magnitude",
        "kedalaman",
        "latitude",
        "longitude",
        "tsunami_probability"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].apply(lambda x: float(x) if pd.notna(x) else None)

    for col in [
        "event_key",
        "kategori",
        "tanggal",
        "jam",
        "wilayah",
        "lokasi_detail",
        "ai_status",
        "ai_rekomendasi",
        "source"
    ]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: None if pd.isna(x) or str(x).strip() == "" else str(x)
            )

    df = df.astype(object)
    df = df.where(pd.notnull(df), None)

    return df


def insert_dataframe(conn, df: pd.DataFrame) -> int:
    db_cols = get_db_columns(conn)

    preferred_cols = [
        "event_key",
        "kategori",
        "tanggal",
        "jam",
        "datetime",
        "event_year",
        "event_month",
        "magnitude",
        "kedalaman",
        "latitude",
        "longitude",
        "wilayah",
        "lokasi_detail",
        "ai_status",
        "ai_rekomendasi",
        "source",
        "tsunami_probability"
    ]

    insert_cols = [
        col for col in preferred_cols
        if col in db_cols and col in df.columns
    ]

    if not insert_cols:
        raise RuntimeError("Tidak ada kolom yang cocok antara DataFrame dan tabel gempa.")

    df_insert = clean_for_database(df[insert_cols])
    records = sanitize_records(df_insert.to_dict(orient="records"))

    if not records:
        return 0

    col_sql = ", ".join(f"`{col}`" for col in insert_cols)
    val_sql = ", ".join(f":{col}" for col in insert_cols)

    sql = text(f"""
        INSERT IGNORE INTO gempa ({col_sql})
        VALUES ({val_sql})
    """)

    total_attempt = 0
    chunk_size = 500

    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        conn.execute(sql, chunk)
        total_attempt += len(chunk)

    return total_attempt


# =========================================================
# PUBLIC FUNCTIONS
# =========================================================

def import_from_file(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        return {
            "status": "error",
            "message": f"File tidak ditemukan: {file_path}"
        }

    ext = os.path.splitext(file_path)[1].lower()

    if ext not in [".csv", ".tsv"]:
        return {
            "status": "skip",
            "message": f"Format file tidak didukung: {ext}"
        }

    filename = os.path.basename(file_path)

    try:
        df_raw = read_dataset_file(file_path)

        if df_raw.empty:
            return {
                "status": "warning",
                "file": filename,
                "message": "File kosong"
            }

        df_ready = prepare_dataframe(df_raw, source_name=filename)

        if df_ready.empty:
            return {
                "status": "warning",
                "file": filename,
                "rows_raw": int(len(df_raw)),
                "message": "Tidak ada baris valid setelah normalisasi. Cek kolom tanggal dan koordinat."
            }

        with engine.begin() as conn:
            before = conn.execute(text("SELECT COUNT(*) FROM gempa")).scalar()
            inserted_attempt = insert_dataframe(conn, df_ready)
            after = conn.execute(text("SELECT COUNT(*) FROM gempa")).scalar()

        return {
            "status": "success",
            "file": filename,
            "rows_raw": int(len(df_raw)),
            "rows_valid": int(len(df_ready)),
            "inserted_attempt": int(inserted_attempt),
            "inserted_actual": int(after - before),
            "total_in_db": int(after)
        }

    except Exception as e:
        logger.exception(f"Import gagal untuk {filename}")

        return {
            "status": "error",
            "file": filename,
            "message": str(e)
        }


def import_all_data_files(data_dir: str, force: bool = False) -> Dict[str, Any]:
    if not os.path.exists(data_dir):
        return {
            "status": "error",
            "message": f"Folder data tidak ditemukan: {data_dir}"
        }

    files = [
        os.path.join(data_dir, name)
        for name in os.listdir(data_dir)
        if name.lower().endswith((".csv", ".tsv"))
    ]

    if not files:
        return {
            "status": "warning",
            "message": "No CSV/TSV files found"
        }

    if force:
        with engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            conn.execute(text("TRUNCATE TABLE gempa"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    results = []
    total_imported_actual = 0

    for file_path in files:
        result = import_from_file(file_path)
        results.append(result)

        if result.get("status") == "success":
            total_imported_actual += result.get("inserted_actual", 0)

    with engine.begin() as conn:
        total_in_db = conn.execute(text("SELECT COUNT(*) FROM gempa")).scalar()

    return {
        "status": "success" if total_imported_actual > 0 else "warning",
        "message": f"Import selesai. Total masuk baru: {total_imported_actual}",
        "total_imported_actual": int(total_imported_actual),
        "total_in_db": int(total_in_db),
        "files": results
    }
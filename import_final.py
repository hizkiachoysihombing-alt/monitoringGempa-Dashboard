# import_final.py
import pandas as pd
import pymysql
import hashlib
from pathlib import Path
from datetime import datetime

print("="*70)
print("🚀 FINAL IMPORT - Dashboard Gempa Indonesia")
print("="*70)

# ================= KONEKSI MYSQL =================
print("\n📡 Connecting to MySQL (localhost:3307)...")
try:
    conn = pymysql.connect(
        host='localhost',
        port=3307,
        user='root',
        password='SIHOMBING24',
        database='gempa_db',
        charset='utf8mb4'
    )
    print("✅ Connected to MySQL!")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit()

# ================= BACA CSV =================
csv_path = Path(__file__).parent / "app" / "data" / "katalog_gempa.csv"
print(f"\n📂 Reading: {csv_path}")

try:
    df = pd.read_csv(csv_path, encoding='utf-8', low_memory=False)
    print(f"✅ Loaded {len(df):,} rows from CSV")
except Exception as e:
    print(f"❌ Failed to read CSV: {e}")
    conn.close()
    exit()

# ================= MAPPING KOLOM =================
# Sesuaikan dengan output cek_csv.py Anda
col_map = {
    'tgl': 'tanggal',      # 2008/11/01
    'ot': 'jam',           # 21:02:43.058
    'lat': 'latitude',
    'lon': 'longitude',
    'depth': 'kedalaman',
    'mag': 'magnitude',
    'remark': 'wilayah',
}

# Rename kolom CSV ke nama database
df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
print(f"🔄 Columns mapped: {list(col_map.keys())} → {list(col_map.values())}")

# ================= KONVERSI TIPE DATA =================
print("\n🔧 Converting data types...")

# Numeric columns
for col in ['magnitude', 'kedalaman', 'latitude', 'longitude']:
    df[col] = pd.to_numeric(df.get(col, 0), errors='coerce').fillna(0)

# Parse tanggal (format: 2008/11/01)
def parse_tanggal(tgl_str):
    if pd.isna(tgl_str) or tgl_str == '':
        return None
    try:
        return datetime.strptime(str(tgl_str).strip(), '%Y/%m/%d')
    except:
        return None

df['datetime'] = df['tanggal'].apply(parse_tanggal)
df['event_year'] = df['datetime'].dt.year if df['datetime'].notna().any() else None
df['event_month'] = df['datetime'].dt.month if df['datetime'].notna().any() else None

# Clean wilayah
df['wilayah'] = df['wilayah'].fillna('Unknown').astype(str).str.strip()
df.loc[df['wilayah'] == 'nan', 'wilayah'] = 'Unknown'

# ================= GENERATE UNIQUE EVENT KEY =================
print("🔑 Generating unique event keys...")

def make_event_key(row, idx):
    """Buat key unik dari kombinasi data"""
    key_parts = [
        str(row.get('tanggal', '')),
        str(row.get('jam', '')),
        str(row.get('magnitude', '')),
        str(row.get('latitude', '')),
        str(row.get('longitude', '')),
        str(idx)
    ]
    key_str = '|'.join(key_parts)
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()

df['event_key'] = [make_event_key(row, idx) for idx, row in df.iterrows()]
df['kategori'] = 'csv'
df['source'] = 'csv_import'
df['ai_status'] = '🟢 RELATIF AMAN'
df['ai_rekomendasi'] = 'Data imported from CSV catalog'

# ================= INSERT KE DATABASE =================
print(f"\n💾 Inserting {len(df):,} records to MySQL...")
cursor = conn.cursor()

sql = """INSERT INTO gempa 
(event_key, kategori, tanggal, jam, datetime, event_year, event_month, 
 magnitude, kedalaman, latitude, longitude, wilayah, 
 ai_status, ai_rekomendasi, source)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

batch_size = 500
inserted = 0
errors = 0

for start in range(0, len(df), batch_size):
    batch = df.iloc[start:start+batch_size]
    
    for idx, row in batch.iterrows():
        try:
            cursor.execute(sql, (
                row['event_key'],
                row['kategori'],
                str(row['tanggal']) if pd.notna(row['tanggal']) else None,
                str(row['jam']) if pd.notna(row['jam']) else None,
                row['datetime'],
                int(row['event_year']) if pd.notna(row['event_year']) else None,
                int(row['event_month']) if pd.notna(row['event_month']) else None,
                float(row['magnitude']),
                float(row['kedalaman']),
                float(row['latitude']),
                float(row['longitude']),
                row['wilayah'],
                row['ai_status'],
                row['ai_rekomendasi'],
                row['source']
            ))
            inserted += 1
        except Exception as e:
            errors += 1
            # Uncomment below to see specific errors:
            # print(f"  ⚠️  Row {idx} error: {e}")
    
    conn.commit()
    progress = min(start + batch_size, len(df))
    print(f"  📊 Progress: {progress:,}/{len(df):,} rows...")

conn.close()

# ================= HASIL =================
print("\n" + "="*70)
print(f"✅ IMPORT SELESAI!")
print(f"   📥 Inserted: {inserted:,} records")
print(f"   ⚠️  Errors: {errors:,} rows skipped")
print(f"   🗄️  Database: gempa_db (MySQL)")
print("="*70)

print("\n💡 Cek hasil di MySQL Workbench:")
print("   USE gempa_db;")
print("   SELECT COUNT(*) AS total FROM gempa;")
print("   SELECT tanggal, wilayah, magnitude, latitude, longitude FROM gempa LIMIT 5;")
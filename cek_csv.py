# cek_csv.py
import pandas as pd
from pathlib import Path

csv_file = Path(__file__).parent / "app" / "data" / "katalog_gempa.csv"
print(f"📂 Membaca: {csv_file}")

df = pd.read_csv(csv_file, encoding='utf-8', nrows=2)
print("\n📋 Kolom yang ditemukan di CSV:")
for i, col in enumerate(df.columns, 1):
    print(f"  {i}. '{col}'")

print("\n📄 2 baris pertama sebagai contoh:")
print(df.head(2).to_string())
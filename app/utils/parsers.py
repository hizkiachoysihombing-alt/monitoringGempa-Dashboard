import re
from typing import Optional, Tuple
from datetime import datetime

BULAN_MAP = {
    "jan": 1, "januari": 1, "january": 1,
    "feb": 2, "februari": 2, "february": 2,
    "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4,
    "mei": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6,
    "jul": 7, "juli": 7, "july": 7,
    "agu": 8, "agustus": 8, "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "okt": 10, "oct": 10, "oktober": 10, "october": 10,
    "nov": 11, "november": 11,
    "des": 12, "dec": 12, "desember": 12, "december": 12
}

def extract_number(value: Optional[str]) -> Optional[float]:
    """Extract angka dari string"""
    if value is None or value == "":
        return None
    try:
        text = str(value).strip().replace(",", ".")
        match = re.search(r"-?\d+(?:[.,]\d+)?", text)
        return float(match.group()) if match else None
    except:
        return None

def parse_coordinate(coord: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Parse koordinat seperti '1.23 LS - 104.56 BT' atau '1.23,104.56'"""
    if not coord:
        return None, None
    
    try:
        # Format: "1.23 LS - 104.56 BT"
        if "-" in str(coord):
            parts = str(coord).split("-")
            if len(parts) >= 2:
                def parse_single(c: str) -> Optional[float]:
                    num = extract_number(c)
                    if num is None:
                        return None
                    c_up = c.upper()
                    # South/West = negative
                    if any(d in c_up for d in ["LS", "BB", "S", "W", "SL"]):
                        return -abs(num)
                    return abs(num)
                
                return parse_single(parts[0]), parse_single(parts[1])
        
        # Format: "1.23,104.56"
        if "," in str(coord):
            parts = str(coord).split(",")
            if len(parts) >= 2:
                return float(parts[0].strip()), float(parts[1].strip())
        
        return None, None
    except:
        return None, None

def parse_datetime_indonesian(date_str: Optional[str], time_str: Optional[str] = None) -> Optional[datetime]:
    """Parse tanggal dan waktu format Indonesia ke datetime object"""
    if not date_str:
        return None
    
    try:
        date_str = str(date_str).strip()
        
        # Coba format ISO: 2024-01-15
        if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
            if time_str:
                time_str = str(time_str).strip().replace(".", ":").split()[0]
                return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            return datetime.strptime(date_str, "%Y-%m-%d")
        
        # Format Indonesia: 15 Januari 2024
        parts = re.split(r"[\s,]+", date_str)
        if len(parts) >= 3:
            day = int(parts[0])
            month_name = parts[1].lower()
            year = int(parts[2])
            month = BULAN_MAP.get(month_name)
            
            if month:
                if time_str:
                    time_str = str(time_str).strip().replace(".", ":").split()[0]
                    return datetime.strptime(f"{year}-{month:02d}-{day:02d} {time_str}", "%Y-%m-%d %H:%M:%S")
                return datetime(year, month, day)
        
        return None
    except Exception as e:
        print(f"Error parsing datetime: {e}")
        return None

def normalize_time(time_str: Optional[str]) -> str:
    """Normalisasi waktu ke format HH:MM:SS"""
    if not time_str:
        return "00:00:00"
    
    try:
        t = str(time_str).replace(".", ":").strip()
        # Hapus timezone
        t = re.sub(r"\s*(WIB|WITA|WIT|UTC|\+[0-9]+)\s*", "", t, flags=re.I)
        
        # Cari pattern waktu
        match = re.search(r"(\d{2}):(\d{2})(?::(\d{2}))?", t)
        if match:
            h, m, s = match.groups()
            return f"{h}:{m}:{s or '00'}"
        return "00:00:00"
    except:
        return "00:00:00"
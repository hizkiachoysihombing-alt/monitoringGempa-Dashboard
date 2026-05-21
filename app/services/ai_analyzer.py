from typing import Tuple, Optional

def analyze_risk(magnitude: Optional[float], depth: Optional[float]) -> Tuple[str, str]:
    mag = float(magnitude) if magnitude and str(magnitude).strip() else 0
    dep = float(depth) if depth and str(depth).strip() else 999
    
    if mag >= 7.0:
        return ("🔴 BAHAYA SANGAT TINGGI", "Evakuasi segera! Gempa sangat kuat.")
    elif mag >= 6.0 and dep <= 70:
        return ("🟠 BAHAYA TINGGI", "Waspadai kerusakan bangunan.")
    elif mag >= 5.0:
        return ("🟡 WASPADA", "Pantau informasi BMKG.")
    else:
        return ("🟢 RELATIF AMAN", "Risiko rendah.")
import math
from datetime import datetime, timezone

class FSRSEngine:
    """
    FSRS (Free Spaced Repetition Scheduler) tabanlı matematiksel bellek motoru.
    Gereksinim: D (Difficulty), S (Stability) ve R (Retrievability - p) hesaplamaları.
    """
    # FSRS v5 standart katsayıları (gerçek insan öğrenme verilerinden optimize edilmiştir)
    PARAMS = {
        'w0': 0.4,      # Başlangıç stabilitesi (kolaylık derecesine göre çarpan)
        'w1': 0.6,      # Zorluğun stabiliteye etkisi
        'w2': 2.4,      # Stabilite taban katsayısı
        'w3': 5.5,      # Başlangıç zorluk merkezi
        'w4': 1.2,      # Zorluk sapma katsayısı
        'decay': -0.5,  # Power Law unutma eğrisi üssü
        'factor': 0.2346 # (19/81) katsayısı
    }

    @classmethod
    def calculate_initial_state(cls, difficulty_label: str) -> dict:
        """
        LLM'den gelen zorluk etiketine ('baslangic', 'orta', 'ileri') göre 
        başlangıç D (Zorluk) ve S (Stabilite) değerlerini hesaplar.
        """
        # Etiket -> Sayısal Derece (1.0 - 10.0)
        diff_map = {'baslangic': 3.0, 'orta': 5.5, 'ileri': 8.0}
        d_grade = diff_map.get(difficulty_label.lower(), 5.5)

        # 1. Başlangıç Zorluğu (D)
        D = max(1.0, min(10.0, cls.PARAMS['w3'] - cls.PARAMS['w4'] * (d_grade - 5.5) / 4.0))

        # 2. Başlangıç Stabilitesi (S) - Gün cinsinden
        S = max(0.1, cls.PARAMS['w0'] * (D ** (-cls.PARAMS['w1'])) * (cls.PARAMS['w2'] + 1))

        return {
            "difficulty": round(D, 4),
            "stability": round(S, 4),
            "retrievability": 1.0, # Yeni öğrenilen bilgi %100 hatırlanır
            "last_review": datetime.now(timezone.utc).isoformat()
        }

    @classmethod
    def calculate_current_retrievability(cls, stability: float, elapsed_days: float) -> float:
        """
        Geçen süreye bağlı olarak hatırlama olasılığını (p değerini) hesaplar.
        FSRS Power Law: R = (1 + factor * t / S)^decay
        """
        if elapsed_days <= 0:
            return 1.0
        
        factor = cls.PARAMS['factor']
        decay = cls.PARAMS['decay']
        
        R = (1.0 + factor * elapsed_days / max(stability, 0.01)) ** decay
        return round(max(0.0, min(1.0, R)), 4)

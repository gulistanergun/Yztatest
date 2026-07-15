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
        label = (difficulty_label or "orta").lower().strip()
        d_grade = diff_map.get(label, 5.5)

        # 1. Başlangıç Zorluğu (D)
        # Daha ileri kavramlar daha yüksek D ve daha düşük başlangıç stabilitesi alır.
        D = max(1.0, min(10.0, d_grade))

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

    @classmethod
    def calculate_elapsed_days_for_retrievability(cls, stability: float, retrievability: float) -> float:
        """
        Verilen S ve hedef R/p için unutma eğrisini tersine çevirip geçen süreyi hesaplar.
        Quiz sonrası kaydedilen p ile graph endpoint'inin tekrar hesapladığı p'yi tutarlı tutar.
        """
        target_r = max(0.01, min(1.0, float(retrievability)))
        if target_r >= 1.0:
            return 0.0

        factor = cls.PARAMS['factor']
        decay = cls.PARAMS['decay']
        stable_s = max(float(stability), 0.01)
        elapsed_days = ((target_r ** (1.0 / decay)) - 1.0) * stable_s / factor
        return max(0.0, elapsed_days)

    @classmethod
    def calculate_quiz_update(cls, current_d: float, current_s: float, score: float) -> dict:
        """
        Quiz skoruna (0.0 - 1.0) göre FSRS Zorluk (D) ve Stabilite (S) değerlerini günceller.
        """
        score = max(0.0, min(1.0, float(score)))
        current_d = max(1.0, min(10.0, float(current_d or 5.5)))
        current_s = max(0.1, float(current_s or 0.5))

        if score >= 0.6:
            # 1. Başarı: Skor oranında stabiliteyi 1.9x ile 2.5x arasında büyütüyoruz (Doğrusal Ölçekleme).
            multiplier = 1.0 + score * 1.5
            new_d = max(1.0, current_d - (score - 0.5))
            new_s = current_s * multiplier
            new_p = 1.0  # Doğrudan %100 hatırlanır
        else:
            # 2. Başarısızlık: Zorluk artar, stabilite %40'ına cezalandırılır
            new_d = min(10.0, current_d + 1.0)
            new_s = max(0.1, current_s * 0.4)
            new_p = max(0.1, min(0.49, score))  # Kırmızı eşikte kalır
            
        return {
            "difficulty": round(new_d, 4),
            "stability": round(new_s, 4),
            "retrievability": round(new_p, 4)
        }

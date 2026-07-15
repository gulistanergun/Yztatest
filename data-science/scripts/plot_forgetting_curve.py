import numpy as np
import matplotlib.pyplot as plt

def main():
    print("Unutma Eğrisi grafiği hazırlanıyor...")
    # 30 günlük bir zaman çizelgesi oluşturalım
    days = np.linspace(0, 30, 100)

    # Farklı yarı ömür değerleri (Örn: Zor konu 2 gün, kolay konu 14 gün)
    half_lives = [2, 5, 10, 20]
    colors = ['#e63946', '#f4a261', '#2a9d8f', '#264653']
    labels = ['Zor/Yeni Konu (h=2)', 'Orta Konu (h=5)', 'Pekiştirilmiş Konu (h=10)', 'Çok İyi Bilinen Konu (h=20)']

    plt.figure(figsize=(10, 6))

    for h, color, label in zip(half_lives, colors, labels):
        # Formül: P = 2^(-t/h)
        prob = 2 ** (-days / h)
        plt.plot(days, prob, label=label, color=color, linewidth=2.5)

    # Yüzde 50 unutma sınırını çizelim (Quiz Ajanı'nın harekete geçeceği eşik)
    plt.axhline(y=0.5, color='gray', linestyle='--', alpha=0.7, label="%50 Hatırlama Sınırı (Quiz Zamanı)")

    plt.title("LearnSphere - HLR Unutma Eğrisi (Forgetting Curve)", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Son Etkileşimden Sonra Geçen Gün Sayısı", fontsize=12)
    plt.ylabel("Hatırlama İhtimali", fontsize=12)
    plt.yticks([0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0], ['0%', '20%', '40%', '50%', '60%', '80%', '100%'])
    plt.legend(title="Konu Durumu (Yarı Ömür)", loc='upper right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Grafiği ekranda göster
    plt.show()

if __name__ == "__main__":
    main()

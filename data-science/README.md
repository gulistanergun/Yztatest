# LearnSphere AI - Veri Bilimi (Data Science)

Bu klasör, LearnSphere AI projesinin **Sprint 1** kapsamındaki veri bilimi (Data Science) çalışmalarını içermektedir. Bu sprint boyunca temel odak noktamız, kullanıcıların öğrenme ve unutma eğrilerini modellemek için bir **HLR (Half-Life Regression)** baseline (temel) modeli geliştirmek ve sentetik verilerle bu modelin çalışabilirliğini kanıtlamaktı.

## 🎯 Neler Yaptık? (Sprint 1)
1. **Veri Üretimi (Data Generation):** Gerçek kullanıcı verimiz henüz olmadığı için, sistemin çalışmasını simüle etmek amacıyla 100 hayali öğrencinin 30 günlük çalışma, test çözme ve etkileşim geçmişini sentetik olarak ürettik.
2. **Model Geliştirme (HLR Baseline):** Sentetik veriler üzerinden kullanıcıların hangi konuyu ne zaman unutacağını tahmin eden **Half-Life Regression** modelinin ilk sürümünü (baseline) kodladık.
3. **Model Çıktıları ve Öneriler:** Modelin tahminlerine göre "Unutma Riski Olan Konular"ı belirleyerek Quiz Ajanı'nın (Quiz Agent) kullanabileceği formatta çıktılar ürettik.

## 🧠 Neden Hazır Kütüphane Kullanmadık?
Hazır makine öğrenmesi kütüphaneleri (Scikit-Learn vb.) standart sınıflandırma yapar ve sadece *"Bu kişi bu konuyu %40 ihtimalle bilir"* gibi genel bir oran verir. 
Biz ise öğrencinin hafızasının zamanla nasıl eridiğini (Ebbinghaus Unutma Eğrisi) tam olarak modelleyebilmek için, Duolingo'nun da kullandığı **Half-Life Regression (HLR)** formülünü dışa bağımlılık olmadan, sıfırdan kodlamayı tercih ettik. 

Kendi yazdığımız bu formül sayesinde modelimiz bize zaman bazlı net bir metrik verebiliyor: *"Bu kişinin bu konudaki hafıza yarı ömrü 14 gündür. 14 gün sonra bilgisi yarı yarıya erimiş olacak."* 
İşte bu **"zamanı" hesaplayabilme yeteneği**, Quiz Ajanı'mızın kullanıcıya tam olarak ne zaman bildirim veya quiz göndermesi gerektiğini nokta atışı bilmesini sağlıyor.


## 📂 Klasör ve Dosya Yapısı

Aşağıda bu klasördeki bileşenlerin ne işe yaradığı detaylandırılmıştır:

```text
data-science/
│
├── 📂 data/ (Girdilerimiz)
│   ├── users.csv              → Yapay kullanıcı profilleri (Ön bilgi, motivasyon)
│   ├── concepts.csv           → Öğrenilen konular ve zorluk dereceleri
│   ├── synthetic_learning_logs.csv → Öğrencilerin simüle edilmiş etkileşim ve sınav geçmişi
│   ├── modeling_dataset.csv   → Modelleme için temizlenmiş ana sınav verisi
│   └── dataset_summary.txt    → Veri seti hakkında özet istatistikler
│
├── 📂 scripts/ (İş Akışı)
│   ├── generate_synthetic_data.py → Sentetik veri üreten motor 
│   ├── train_forgetting_baseline.py → Modelimizi eğiten motor 
│   └── plot_forgetting_curve.py   → Modelin unutma eğrisi grafiğini çizen araç
│
├── 📂 notebooks/ (Sunum & Görsel Alan)
│   └── 01_hlr_baseline.ipynb  → süreci adım adım gösteren notebook
│
└── 📂 outputs/ (Model Çıktılarımız)
    ├── model_metrics.json     → Modelimizin başarı skorları (Accuracy, AUC vb.)
    ├── feature_weights.csv    → Modelin hangi özelliği ne kadar önemsediği (Ağırlıklar)
    └── at_risk_recommendations.csv → Quiz Ajanı'na gönderilecek "Unutma Riski Olan Konular"
```


## 🚀 Çalıştırma Adımları (Tekrar Üretmek İçin)

Eğer sistemi kendi ortamınızda baştan çalıştırmak isterseniz:

1. **Önce sentetik verileri üretin:**
   ```bash
   python scripts/generate_synthetic_data.py
   ```
   *(Bu işlem `data/` klasöründeki dosyaları güncelleyecektir.)*

2. **Ardından bu verilerle modeli eğitin:**
   ```bash
   python scripts/train_forgetting_baseline.py
   ```
   *(Bu işlem eğitim sonucunu `outputs/` klasörüne yansıtacaktır.)*

Detaylı bir anlatım ve grafiksel çıktılar için `notebooks/01_hlr_baseline.ipynb` dosyasını çalıştırarak inceleyebilirsiniz.

# **Takım - LearnSphere AI**

### **`LearnSphere AI`**

> **"YouTube izle, Gemini'ye sor — sistem geri kalanını halleder."**

---

## **Takım Üyeleri**

| Ad | Görev |
|------|-------|
| **Ömer Semih Uzun** | Backend, AI Pipeline, Knowledge Graph, Chrome Extension |
| **[Takım Arkadaşı 1]** | [Görevi] |
| **[Takım Arkadaşı 2]** | [Görevi] |

---

## **Ürün Açıklaması**

**LearnSphere AI**, kullanıcının web tarayıcısındaki öğrenme aktivitelerini otonom olarak izleyip, içinden teknik kavramları çıkaran ve bunları interaktif bir **Bilgi Grafiği (Knowledge Graph)** olarak görselleştiren yapay zeka destekli bir "İkinci Beyin" uygulamasıdır. 

Kullanıcılar normal şekilde YouTube videoları izlerken veya Gemini/ChatGPT gibi yapay zeka araçlarıyla araştırma yaparken, Chrome eklentimiz arka planda sessizce çalışarak bu eğitimsel içerikleri yakalar. Toplanan veriler, **Gemini 2.0 Flash** modeli ile analiz edilir ve öğrenilen konular (örn: Python, Docker, Pandas) arasındaki ilişkiler **Neo4j** graf veritabanında haritalandırılır. Aynı zamanda metinler vektörleştirilerek **Qdrant**'a kaydedilir. Kullanıcılar, oluşturulan bu etkileşimli zihin haritası üzerinde gezinebilir ve "İkinci Beyin" özelliği sayesinde sadece kendi öğrendikleri bağlamlar üzerinden yapay zekaya sorular sorarak (RAG Chat) bilgilerini tazeleyebilirler.

<details>
<summary><strong>Ürün Özellikleri</strong></summary>
  
---

### 1. Otonom Veri Toplama
- **Chrome Extension:** YouTube, Gemini ve ChatGPT sekmelerinde çalışır.
- **Sessiz Çalışma:** Kullanıcının hiçbir butona basmasına gerek kalmadan, sadece izleyerek veya sorarak veriyi yakalar.
- **Veri Temizleme:** Gereksiz UI metinlerini ve PII (kişisel tanımlanabilir bilgi) verilerini filtreler.

### 2. AI Destekli Kavram Çıkarımı
- Gemini 2.0 Flash modeli kullanılarak ham sohbet/video verilerinden konu, kategori ve zorluk derecesi çıkarılır.
- Eğitimsel olmayan "gürültü" niteliğindeki sohbetler sistem tarafından otomatik reddedilir.

### 3. Bilgi Grafiği (Knowledge Graph) & Zihin Haritası
- Neo4j tabanlı ağ yapısı ile öğrenilen her şey birbiriyle ilişkilendirilir.
- Fizik kurallarıyla çalışan interaktif **Living Mind Tree** arayüzünde öğrenme ağı görselleştirilir.

### 4. İkinci Beyin (RAG Sohbet)
- Qdrant vektör veritabanında saklanan veriler üzerinden semantik arama yapılır.
- Kullanıcı bir soru sorduğunda, sistem tüm interneti değil **yalnızca kullanıcının kendi öğrendiği kaynakları** referans alarak cevap verir.

### 5. Kaynak Yönetimi
- Sol paneldeki kaynak listesi üzerinden istenmeyen veriler silinebilir. Silinen veri hem grafikten hem de vektör hafızadan kaldırılır.

---
</details>

<details>
<summary><strong>Hedef Kitle</strong></summary>

---

### Kendi Kendine Öğrenenler (Self-learners)
- Farklı kaynaklardan (video, makale, yapay zeka) edindikleri bilgileri tek bir yerde birleştirmek isteyenler.

### Yazılım Geliştiriciler ve Mühendisler
- Yeni teknolojileri, dilleri veya kütüphaneleri öğrenirken öğrendikleri kavramları birbiriyle ilişkilendirmek isteyen profesyoneller.

### Öğrenciler ve Akademisyenler
- Araştırma yaparken karşılaştıkları kaynakları ve çıkardıkları notları görsel bir ağ (mind map) üzerinde görüp daha kalıcı öğrenme hedefleyenler.

### Kişisel Verimlilik (Productivity) Odaklılar
- Notion, Obsidian gibi uygulamalara manuel not girmek yerine, sürecin tamamen otonom çalışmasını isteyen kullanıcılar.

---
</details>

## **Product Backlog URL**

[Miro Backlog Board](https://miro.com/app/board/uXjVHCRzr6Q=/?share_link_id=571188315568)

---

## **Sprints**

<details>
<summary><strong>Sprint 1</strong></summary>

---

### Sprint Notları
**Sprint 1** sürecinde projenin temel altyapısı (MVP) başarılı bir şekilde kurulmuştur. Hedeflenen özellikler uçtan uca çalışır hale getirilmiştir:
- **FastAPI** backend ayağa kaldırıldı ve veri işleme (ingest) endpointleri yazıldı.
- **Chrome Extension** geliştirildi. ChatGPT, Gemini ve YouTube üzerinden başarılı bir şekilde otomatik veri çekimi sağlandı.
- **Neo4j** ve **Qdrant** veritabanı entegrasyonları docker üzerinden yapılandırıldı. Gemini AI modeli bağlanarak başarılı şekilde "Kavram Çıkarımı" test edildi.
- **React** frontend ile uçuşan interaktif zihin haritası (Living Mind Tree) arayüzü kodlandı.
- Vektör tabanlı **İkinci Beyin (RAG Chat)** sistemi entegre edilip çalıştırıldı.

### Proje Yönetimi
- Sprint board'umuz Miro üzerinde oluşturuldu ve product backlog item'ları belirlendi. 
- İlk sprint task'leri atanarak MVP gereksinimleri tamamlandı.

### Ekran Görüntüleri
*(Sprint 1 ekran görüntüleri eklenecek...)*
- `Ana Sayfa Zihin Haritası`
- `Chrome Eklentisi Veri Toplama Anı`
- `İkinci Beyin Sohbet Ekranı`

---
</details>

<br>

> **Not:** Aşağıdaki bölüm geliştiriciler için projenin teknik kurulumunu ve mimarisini içermektedir.

---

## 🏗️ Teknik Mimari

```
Chrome Extension  →  FastAPI Backend  →  Neo4j (Graph DB)
     (Veri)              (Zeka)              (İlişkiler)
                            ↓
                     Gemini 2.0 Flash   →  Qdrant (Vector DB)
                     (Kavram Çıkarımı)       (RAG Chat)
                            ↓
                     React Frontend
                     (Living Mind Tree)
```

## 🚀 Kurulum

### Gereksinimler
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Google Gemini API Key ([buradan al](https://aistudio.google.com/app/apikey))

### 1. Repo'yu klonla
```bash
git clone https://github.com/omersemihuzun/Yztatest.git
cd Yztatest
```

### 2. Veritabanlarını başlat (Docker)
```bash
cd backend
docker-compose up -d
```

### 3. Backend kurulumu
```bash
# .env dosyasını oluştur
cp .env.example .env
# .env dosyasını aç, GOOGLE_API_KEY'i kendi API key'inle değiştir

# Bağımlılıkları yükle
pip install -r requirements.txt

# Backend'i başlat
uvicorn app.main:app --reload --port 8080
```

### 4. Frontend kurulumu
```bash
cd ../frontend
npm install
npm run dev
```

### 5. Chrome Extension kurulumu
1. Chrome'da `chrome://extensions/` adresine git
2. "Geliştirici modu"nu aç (sağ üst)
3. "Paketlenmemiş öğe yükle" → `extension/` klasörünü seç

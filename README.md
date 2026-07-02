# 🧠 LearnSphere AI

> **"YouTube izle, Gemini'ye sor — sistem geri kalanını halleder."**

LearnSphere AI, kullanıcının web tarayıcısındaki öğrenme aktivitelerini otonom olarak izleyip, içinden teknik kavramları çıkaran ve bunları interaktif bir **Bilgi Grafiği (Knowledge Graph)** olarak görselleştiren yapay zeka destekli bir "İkinci Beyin" uygulamasıdır.

---

## 🏗️ Mimari

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

---

## 🎯 Özellikler

| Özellik | Açıklama |
|---------|----------|
| 🔍 **Otonom Veri Toplama** | YouTube, Gemini, ChatGPT'yi arka planda izler |
| 🧠 **AI Kavram Çıkarımı** | Gemini 2.0 Flash ile teknik kavramları otomatik çıkarır |
| 🕸️ **Knowledge Graph** | Neo4j üzerinde kavramlar arası ilişki ağı |
| 💬 **RAG Sohbet** | "Python nedir?" → kendi öğrendiklerinden cevap verir |
| 🗑️ **Kaynak Silme** | İstenmeyen kaynakları haritadan temizler |
| ⏱️ **Auto-Processor** | Her 10 saniyede bir yeni verileri işler |

---

## 📁 Proje Yapısı
```
LearnSphere_AI/
├── backend/
│   ├── app/
│   │   ├── core/          # Config, Logging
│   │   ├── db/            # Neo4j, Qdrant clients
│   │   ├── models/        # Pydantic schemas
│   │   ├── routers/       # API endpoints
│   │   └── services/      # İş mantığı
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── .env.example       # ← Bunu kopyala, .env yap
├── extension/             # Chrome Extension
│   ├── content.js         # DOM gözlemcisi
│   ├── background.js      # Network worker
│   ├── config.js          # Backend URL
│   └── youtube.js         # YouTube özel scraper
└── frontend/              # React + Vite
    └── src/
        └── components/    # MindMap, Sidebar, ChatBar...
```

---

## 🤝 Ekip

- **Ömer Semih Uzun** — Backend, AI Pipeline, Knowledge Graph, Chrome Extension

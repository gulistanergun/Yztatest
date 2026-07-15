// ============================================================
// LearnSphere Extension — Merkezi Konfigürasyon
// Sprint 1 için bu dosyada n8n Webhook URL'ini güncelle.
// ============================================================

const LS_CONFIG = {
  // FastAPI Backend — direkt bağlantı
  BACKEND_URL: "http://127.0.0.1:8080/api/v1/ingest",

  // Kaç ms sonra veriyi gönderelim (streaming bittikten sonra)
  DEBOUNCE_DELAY_MS: 2500,

  // Aynı konuşmayı kaç dakikada bir tekrar gönderebiliriz
  RESEND_COOLDOWN_MINUTES: 5,

  // Debug modunda console logları aktif
  DEBUG: true,
};

// Hem content script (classic) hem service worker (module) erişebilsin
globalThis.LS_CONFIG = LS_CONFIG;

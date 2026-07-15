// ============================================================
// LearnSphere Extension — Background Service Worker
// Content script'ten gelen mesajları alır ve backend'e POST atar.
// Content script'in bizzat fetch yapması CORS sorununa yol açar,
// bu yüzden tüm network çağrıları buradan yapılır.
// Ek: sağ tık menüsüyle seçili metni LearnSphere'e gönderme.
// ============================================================

// config ve PII filtresi (globalThis üzerinden değer bırakırlar)
import "./config.js";
import "./utils/pii_filter.js";

const SEND_QUEUE = [];
let isSending = false;
let queueRestored = false;

// Service worker uykuya dalıp uyandığında bellekteki kuyruk kaybolur.
// Bu yüzden kuyruğun bir kopyası chrome.storage.local'da tutulur.
async function persistQueue() {
  try {
    await chrome.storage.local.set({ ls_send_queue: SEND_QUEUE });
  } catch (e) {
    console.warn("[LearnSphere BG] Kuyruk kaydedilemedi:", e.message);
  }
}

async function restoreQueue() {
  if (queueRestored) return;
  queueRestored = true;
  try {
    const { ls_send_queue } = await chrome.storage.local.get("ls_send_queue");
    if (Array.isArray(ls_send_queue) && ls_send_queue.length > 0) {
      SEND_QUEUE.push(...ls_send_queue);
      console.log(`[LearnSphere BG] ${ls_send_queue.length} bekleyen mesaj geri yüklendi.`);
    }
  } catch (e) {
    console.warn("[LearnSphere BG] Kuyruk geri yüklenemedi:", e.message);
  }
}

/**
 * Mesaj kuyruğunu sırayla işler (seri gönderim, spam yapmaz).
 */
async function processQueue() {
  if (isSending || SEND_QUEUE.length === 0) return;
  isSending = true;

  const payload = SEND_QUEUE.shift();
  await persistQueue();

  try {
    const response = await fetch(payload.webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload.data),
    });

    if (!response.ok) {
      throw new Error(`n8n HTTP ${response.status}: ${response.statusText}`);
    }

    console.log(`[LearnSphere BG] ✅ Başarıyla gönderildi → ${payload.data.platform}`);
  } catch (error) {
    console.error("[LearnSphere BG] ❌ Gönderim başarısız:", error.message);
    // Retry: Hatalı mesajı kuyruğun sonuna geri koy (max 3 deneme)
    if ((payload.retryCount || 0) < 3) {
      SEND_QUEUE.push({ ...payload, retryCount: (payload.retryCount || 0) + 1 });
      await persistQueue();
      console.warn(`[LearnSphere BG] 🔄 Yeniden deneme kuyruğa eklendi (${payload.retryCount + 1}/3)`);
    } else {
      console.error("[LearnSphere BG] ⛔ Maksimum deneme sayısına ulaşıldı, mesaj düşürüldü.");
    }
  } finally {
    isSending = false;
    // Kuyrukta başka mesaj varsa devam et
    if (SEND_QUEUE.length > 0) {
      setTimeout(processQueue, 500);
    }
  }
}

// Content script'ten gelen "SEND_TO_BACKEND" mesajlarını dinle
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SEND_TO_BACKEND") {
    restoreQueue().then(() => {
      SEND_QUEUE.push({
        webhookUrl: message.backendUrl,
        data: message.data,
        retryCount: 0,
      });
      persistQueue();
      processQueue();
    });
    sendResponse({ status: "queued" });
  }
  return true;
});

// Service worker her uyandığında bekleyen kuyruğu işlemeyi dene
restoreQueue().then(processQueue);

// ============================================================
// Sağ tık menüsü: "Seçimi LearnSphere'e kaydet"
// Otonom yakalamanın tamamlayıcısı — desteklenmeyen sitelerde
// (blog, dokümantasyon vb.) kullanıcıya kontrol verir.
// ============================================================
const MENU_ID = "ls-save-selection";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_ID,
    title: "Seçimi LearnSphere'e kaydet",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== MENU_ID) return;

  const selection = (info.selectionText || "").trim();
  if (selection.length < 20) {
    console.warn("[LearnSphere BG] Seçim çok kısa, gönderilmedi (min 20 karakter).");
    return;
  }

  const pageTitle = tab?.title || "Web sayfası";
  const payload = {
    platform: "Web",
    url: info.pageUrl || tab?.url || "",
    timestamp: new Date().toISOString(),
    session_id: `Web_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    data: {
      question: globalThis.sanitizePII(`[Seçim] ${pageTitle}`),
      answer: globalThis.sanitizePII(selection),
    },
  };

  restoreQueue().then(() => {
    SEND_QUEUE.push({
      webhookUrl: globalThis.LS_CONFIG.BACKEND_URL,
      data: payload,
      retryCount: 0,
    });
    persistQueue();
    processQueue();
    console.log("[LearnSphere BG] ✂️ Seçim kuyruğa eklendi:", pageTitle);
  });
});

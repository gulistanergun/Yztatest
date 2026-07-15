// ============================================================
// LearnSphere Extension — PII (Kişisel Veri) Filtresi
// Hassas bilgileri gönderilmeden önce temizler.
// ============================================================

const PII_PATTERNS = [
  // Şifre ifadeleri
  { pattern: /(?:şifre(?:m|si|niz)?|password|parola)\s*[:=]?\s*\S+/gi, replacement: "[ŞİFRE GİZLENDİ]" },

  // TC Kimlik Numarası (11 haneli)
  { pattern: /\b[1-9][0-9]{10}\b/g, replacement: "[TC KİMLİK GİZLENDİ]" },

  // Kredi Kartı (13-19 haneli, boşluklu/tiresiz)
  { pattern: /\b(?:\d[ -]?){13,19}\b/g, replacement: "[KART NO GİZLENDİ]" },

  // E-posta adresleri
  { pattern: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, replacement: "[E-POSTA GİZLENDİ]" },

  // Türkiye'ye özgü telefon numaraları
  { pattern: /(?:\+90|0090|0)?\s*(?:\d{3,4})[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}/g, replacement: "[TELEFON GİZLENDİ]" },

  // API key / Token — bilinen öneklerle hedefli eşleşme.
  // (Eski hali 30+ karakterlik HER diziyi siliyordu; bu, kod örneklerindeki
  // hash/base64/uzun değişken adlarını da bozuyordu.)
  {
    pattern: /\b(?:sk-[A-Za-z0-9_\-]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_\-]{20,}|xox[bap]-[A-Za-z0-9\-]{16,}|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})\b/g,
    replacement: "[TOKEN/ANAHTAR GİZLENDİ]",
  },
  // "api_key: xxxx", "token=xxxx" gibi açıkça etiketlenmiş sırlar
  { pattern: /\b(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*['"]?[A-Za-z0-9_\-]{12,}['"]?/gi, replacement: "[TOKEN/ANAHTAR GİZLENDİ]" },
];

/**
 * Metindeki PII'yı temizler ve temizlenmiş versiyonu döner.
 * @param {string} text - Ham metin
 * @returns {string} - PII'sı temizlenmiş metin
 */
function sanitizePII(text) {
  if (!text || typeof text !== "string") return "";
  let sanitized = text;
  PII_PATTERNS.forEach(({ pattern, replacement }) => {
    sanitized = sanitized.replace(pattern, replacement);
  });
  return sanitized;
}

// Hem content script (classic) hem service worker (module) erişebilsin
globalThis.sanitizePII = sanitizePII;

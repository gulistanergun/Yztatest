// ============================================================
// LearnSphere Extension — Passive Prompting (Pasif Uyarı)
// ============================================================

(function () {
  "use strict";

  // Sadece ana çerçevede (iframe içinde değil) çalışmasını sağlayalım
  if (window.top !== window.self) return;

  // Regex özel karakterlerini kaçır (kavram isimlerinde "(CNN)" gibi parantezler olabiliyor)
  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  // Backend'den (background.js'nin periyodik çektiği) gerçek riskli kavram listesini oku
  chrome.storage.local.get(["atRiskConcepts"], function (result) {
    const atRiskConcepts = result.atRiskConcepts || [];
    if (atRiskConcepts.length === 0) return; // Henüz veri yok veya risk altında kavram yok

    // Sayfa tam yüklendikten sonra ufak bir bekleme süresi (Performans için)
    setTimeout(() => {
      scanPageAndPrompt(atRiskConcepts);
    }, 2000);
  });

  function scanPageAndPrompt(atRiskConcepts) {
    const pageText = document.body.innerText.toLowerCase();

    // Regex ile tam kelime/ifade eşleşmesi ara
    let found = null;
    for (const concept of atRiskConcepts) {
      const regex = new RegExp(`\\b${escapeRegex(concept.name.toLowerCase())}\\b`, "i");
      if (regex.test(pageText)) {
        found = concept;
        break;
      }
    }

    if (found) {
      showPassivePrompt(found);
    }
  }

  function showPassivePrompt(concept) {
    const keyword = concept.name;
    const days = concept.days_since_last_studied;
    const daysText = typeof days === "number"
      ? `${Math.round(days)} gün önce`
      : "bir süre önce";
    // Eğer bildirim halihazırda ekrandaysa ikinciyi oluşturma
    if(document.getElementById('learnsphere-passive-prompt')) return;

    const promptDiv = document.createElement('div');
    promptDiv.id = 'learnsphere-passive-prompt';
    
    // Şık, modern ve rahatsız etmeyen arayüz tasarımı
    promptDiv.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      background-color: #ffffff;
      border-left: 5px solid #ef4444; /* Kırmızı uyarı şeridi */
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
      padding: 16px 20px;
      border-radius: 12px;
      z-index: 2147483647; /* En üstte görünmesi için */
      font-family: system-ui, -apple-system, sans-serif;
      max-width: 320px;
      animation: lsSlideIn 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    `;
    
    // Animasyon CSS'i
    const style = document.createElement('style');
    style.innerHTML = `
      @keyframes lsSlideIn {
        from { transform: translateY(100px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
      }
    `;
    document.head.appendChild(style);

    promptDiv.innerHTML = `
      <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px;">
        <strong style="color: #1f2937; font-size: 15px;">LearnSphere Asistanı</strong>
        <button id="ls-close-btn" style="background: none; border: none; cursor: pointer; color: #9ca3af; font-size: 18px; line-height: 1; padding: 0;">&times;</button>
      </div>
      <p style="margin: 0 0 12px 0; font-size: 13px; color: #4b5563; line-height: 1.5;">
        Şu an okuduğun <strong style="color: #ef4444;">${keyword}</strong> konusunu ${daysText} çalışmıştın ve unutmak üzeresin. 1 dakikalık hızlı bir quiz ister misin?
      </p>
      <div style="display: flex; gap: 8px;">
        <button id="ls-quiz-btn" style="background: #3b82f6; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500;">
          Evet, Quize Başla
        </button>
      </div>
    `;

    document.body.appendChild(promptDiv);

    // Buton İşlevleri: quiz açma işini background.js'ye devret (content script'in
    // chrome.tabs API erişimi yok), o da LearnSphere frontend'ini ilgili kavramla açar.
    document.getElementById('ls-quiz-btn').addEventListener('click', () => {
      chrome.runtime.sendMessage({ type: "OPEN_QUIZ", concept: keyword });
      promptDiv.remove();
    });

    document.getElementById('ls-close-btn').addEventListener('click', () => {
      promptDiv.remove();
    });
  }
})();
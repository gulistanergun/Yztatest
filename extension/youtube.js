// ============================================================
// LearnSphere Extension — YouTube Content Script
// Görevleri:
// 1. İzlenen video başlığını yakala
// 2. YouTube'un gizli transcript API'sinden altyazı çek
// 3. Veriyi PII temizleyerek backend'e gönder
// ============================================================

(function () {
  "use strict";

  if (!window.location.hostname.includes("youtube.com")) return;

  let lastSentVideoId = null;
  let transcriptTimer = null;

  // ---- Video ID'yi URL'den çek ----
  function getVideoId() {
    const params = new URLSearchParams(window.location.search);
    return params.get("v");
  }

  // ---- Sayfa başlığından video adını çek ----
  function getVideoTitle() {
    const el = document.querySelector("h1.ytd-watch-metadata yt-formatted-string");
    return el ? el.innerText.trim() : document.title.replace(" - YouTube", "").trim();
  }

  // ---- YouTube'un dahili transcript API'sini kullan ----
  // NOT: Content script izole dünyada çalıştığı için window.ytInitialPlayerResponse
  // BURADAN OKUNAMAZ. Track bilgisi, MAIN world'de çalışan yt_page_bridge.js'ten
  // postMessage ile gelir (aşağıdaki listener'da yakalanır).
  let bridgeTracks = null;
  let bridgeVideoId = null;

  window.addEventListener("message", (ev) => {
    if (ev.source !== window || !ev.data || ev.data.source !== "LS_YT_BRIDGE") return;
    bridgeTracks = ev.data.tracks;
    bridgeVideoId = ev.data.videoId;
  });

  // Köprüden track bilgisini iste ve kısa süre bekle
  function requestTracksFromBridge(videoId, timeoutMs = 4000) {
    return new Promise((resolve) => {
      if (bridgeTracks && bridgeVideoId === videoId) {
        resolve(bridgeTracks);
        return;
      }
      window.postMessage({ source: "LS_YT_REQUEST" }, window.location.origin);
      const started = Date.now();
      const poll = setInterval(() => {
        if (bridgeTracks && bridgeVideoId === videoId) {
          clearInterval(poll);
          resolve(bridgeTracks);
        } else if (Date.now() - started > timeoutMs) {
          clearInterval(poll);
          resolve(bridgeTracks); // videoId eşleşmese de eldekiyle dene
        }
      }, 250);
    });
  }

  async function fetchTranscript(videoId) {
    try {
      const tracks = await requestTracksFromBridge(videoId);
      if (!tracks || tracks.length === 0) return null;

      // Türkçe varsa onu, yoksa ilk track'i kullan
      const preferred =
        tracks.find((t) => t.languageCode === "tr") || tracks[0];
      const url = preferred.baseUrl + "&fmt=json3";

      const response = await fetch(url);
      if (!response.ok) return null;

      const data = await response.json();
      // Tüm segmentlerin metnini birleştir
      const fullText = data.events
        .filter((e) => e.segs)
        .map((e) => e.segs.map((s) => s.utf8).join(""))
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();

      return fullText.length > 50 ? fullText : null;
    } catch (e) {
      console.warn("[LearnSphere YouTube] Transcript alınamadı:", e.message);
      return null;
    }
  }

  // ---- Arama sorgusunu URL'den çek ----
  function getSearchQuery() {
    if (!window.location.pathname.includes("/results")) return null;
    return new URLSearchParams(window.location.search).get("search_query");
  }

  // ---- Veriyi Backend'e Gönder ----
  function sendToBackend(payload) {
    const clean = {
      ...payload,
      data: {
        question: sanitizePII(payload.data.question),
        answer: sanitizePII(payload.data.answer),
      },
    };

    if (LS_CONFIG.DEBUG) {
      console.log("[LearnSphere YouTube] Gönderiliyor:", clean);
    }

    chrome.runtime.sendMessage({
      type: "SEND_TO_BACKEND",
      backendUrl: LS_CONFIG.BACKEND_URL,
      data: clean,
    });
  }

  // ---- Video Sayfasını İşle ----
  async function handleVideoPage(videoId) {
    if (videoId === lastSentVideoId) return; // Aynı videoyu tekrar gönderme
    lastSentVideoId = videoId;

    const title = getVideoTitle();
    const transcript = await fetchTranscript(videoId);

    sendToBackend({
      platform: "YouTube",
      url: window.location.href,
      timestamp: new Date().toISOString(),
      session_id: `YouTube_${videoId}_${Date.now()}`,
      data: {
        // Soru: video başlığı (kullanıcının ne öğrenmeye çalıştığı)
        question: `[YouTube Video] ${title}`,
        // Cevap: transcript varsa onu, yoksa "transcript yok" notu
        answer: transcript || `[Transcript yok] Video: ${title}`,
      },
    });
  }

  // ---- Arama Sorgusunu İşle ----
  function handleSearchPage() {
    const query = getSearchQuery();
    if (!query) return;

    const searchId = `YouTube_search_${encodeURIComponent(query)}`;
    if (searchId === lastSentVideoId) return;
    lastSentVideoId = searchId;

    sendToBackend({
      platform: "YouTube",
      url: window.location.href,
      timestamp: new Date().toISOString(),
      session_id: searchId,
      data: {
        question: `[YouTube Arama] ${query}`,
        answer: `Kullanıcı "${query}" ile ilgili video aradı.`,
      },
    });
  }

  // ---- URL Değişimini İzle (SPA navigasyon için) ----
  // YouTube tek sayfalı uygulama olduğu için normal load olayı tetiklenmez.
  // Bunun yerine navigation API veya MutationObserver kullanırız.
  let lastUrl = window.location.href;
  const navObserver = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;

      // Yeni sayfanın yüklenmesi için kısa bir gecikme bırak
      clearTimeout(transcriptTimer);
      transcriptTimer = setTimeout(() => {
        const videoId = getVideoId();
        if (videoId) {
          handleVideoPage(videoId);
        } else if (window.location.pathname.includes("/results")) {
          handleSearchPage();
        }
      }, 3000);
    }
  });

  // İlk yükleme
  setTimeout(() => {
    navObserver.observe(document.body, { childList: true, subtree: true });
    const videoId = getVideoId();
    if (videoId) handleVideoPage(videoId);
    else if (window.location.pathname.includes("/results")) handleSearchPage();
  }, 3000);
})();

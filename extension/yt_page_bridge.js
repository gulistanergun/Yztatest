// ============================================================
// LearnSphere Extension — YouTube Sayfa Köprüsü (MAIN world)
// Content script'ler izole dünyada çalıştığı için sayfanın
// window.ytInitialPlayerResponse objesine erişemez. Bu script
// manifest'te "world": "MAIN" ile sayfa bağlamında çalışır ve
// altyazı track bilgisini postMessage ile izole tarafa iletir.
// ============================================================

(function () {
  "use strict";

  function sendTracks() {
    try {
      const pr = window.ytInitialPlayerResponse;
      const tracks =
        pr?.captions?.playerCaptionsTracklistRenderer?.captionTracks || null;
      window.postMessage(
        {
          source: "LS_YT_BRIDGE",
          videoId: pr?.videoDetails?.videoId || null,
          tracks: tracks
            ? tracks.map((t) => ({
                baseUrl: t.baseUrl,
                languageCode: t.languageCode,
              }))
            : null,
        },
        window.location.origin
      );
    } catch (e) {
      /* sayfa objesi henüz hazır değilse sessizce geç */
    }
  }

  // İlk yükleme
  setTimeout(sendTracks, 1500);

  // YouTube SPA navigasyonu tamamlanınca (yt kendi event'ini yayınlar)
  window.addEventListener("yt-navigate-finish", () => setTimeout(sendTracks, 1500));

  // İzole taraf açıkça isterse tekrar gönder
  window.addEventListener("message", (ev) => {
    if (ev.source === window && ev.data && ev.data.source === "LS_YT_REQUEST") {
      sendTracks();
    }
  });
})();

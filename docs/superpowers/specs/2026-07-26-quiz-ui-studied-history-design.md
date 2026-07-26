# Quiz Arayüzü + STUDIED Geçmişi — Tasarım

## Kapsam

Sprint 3 backlog'undaki iki açık madde:

1. **Quiz arayüzü** — mevcut `/api/v1/quiz/generate` ve `/api/v1/quiz/submit` backend'ini
   kullanan bir frontend akışı. Soru üretimi backend tarafı zaten tamamlanmış durumda.
2. **STUDIED geçmişi** — quiz sonucu gönderildiğinde `(User)-[:STUDIED]->(Concept)`
   ilişkisinin yazılması.

Kapsam dışı (bilinçli olarak, ayrı backlog maddeleri): login/kayıt ekranı, çok kullanıcılı
auth, kavram çıkarımı (extraction) sırasında STUDIED yazımı, pytest altyapısı kurulumu.

## Kararlar

- **User modeli:** Singleton `User {id: 'local_user'}` node. Login/kayıt ekranı YOK —
  tamamen arka planda, sessizce oluşur. İleride gerçek çoklu profil ihtiyacı çıkarsa
  şema zaten uyumlu (yeni `User` node'ları eklenir, migrasyon gerekmez).
  `user_id_unique` constraint zaten `neo4j_client.py`'de mevcut, hiç kullanılmamıştı.
- **STUDIED tetikleyicisi:** Sadece `/quiz/submit` çağrıldığında yazılır. Kavram çıkarımı
  (extraction) akışına dokunulmaz.
- **Quiz giriş noktaları:** (a) `NodeDetailsPanel`'de "Quiz Çöz" butonu — seçili kavramla
  başlar. (b) Header'da "🎯 Bugünün Quizi" butonu — `/quiz/recommendations?limit=1` ile
  en riskli kavramı otomatik seçip aynı modalı açar.
- **Akış:** Adım adım (tek soru, anlık doğru/yanlış geri bildirimi + açıklama), ama dar yan
  panele sıkıştırmak yerine ortada ferah bir modal/overlay olarak sunulur.
- **Görsel yön:** Yeni bir palet icat edilmiyor — mevcut "köz/gece" tema (`--gece`, `--kor`,
  `--nane`, `--tehlike`, `--panel`, `--cizgi` + Space Grotesk/IBM Plex Sans/JetBrains Mono)
  aynen kullanılıyor. İmza öğe: doğru cevapta kart `--nane` rengiyle sıcak bir halo ile
  parlar, yanlışta `--tehlike` ile söner — MindMap'teki node glow efektiyle aynı görsel
  dilde, "kavramın haritadaki davranışının küçük bir önizlemesi" hissi.

## Mimari

### Backend (minimal değişiklik)

`backend/app/services/graph_service.py` → `update_concept_after_quiz()` içine, mevcut FSRS
güncellemesiyle **aynı Neo4j session** içinde:

```cypher
MERGE (u:User {id: 'local_user'})
MERGE (u)-[r:STUDIED]->(c:Concept {name: $concept_name})
ON CREATE SET r.first_studied = datetime(), r.attempts = 1
ON MATCH SET r.attempts = coalesce(r.attempts, 0) + 1
SET r.last_score = $score, r.last_studied = datetime()
```

`/api/v1/quiz/submit` sözleşmesi (request/response şeması) değişmiyor — sadece yan etkisi
genişliyor.

### Frontend (yeni bileşen)

- `frontend/src/components/QuizModal.jsx` — quiz akışının tamamını (üretim çağrısı, soru
  gösterimi, cevap/geri bildirim, skor, submit çağrısı) yöneten bağımsız, otonom bileşen.
  `concept` prop'u alır, `onClose` ile kapanır.
- `App.jsx`: yeni state `quizConcept` (string|null). Modal açık/kapalı ve hangi kavramla
  açıldığını kontrol eder. Modal kapanınca `fetchGraph()` tekrar çağrılır (harita renkleri
  güncel `fsrs_p`'yi yansıtsın).
- `NodeDetailsPanel.jsx`: "Quiz Çöz" butonu eklenir (`onStartQuiz(node.label)` prop'u, mevcut
  `onShowPath` deseniyle aynı şekilde kablolanır). Mevcut `canShowPath` koşuluyla aynı kural
  geçerli: küme (`isCluster`) veya sanal (`isVirtual`) node'larda buton gösterilmez — quiz
  sadece gerçek kavramlar için anlamlı.
- `App.jsx` header buton satırı: "🎯 Bugünün Quizi" butonu eklenir. `/quiz/recommendations`
  boş liste dönerse (harita boşsa/hiç kavram yoksa) buton yerine kısa bir uyarı gösterilir
  ("Henüz quiz üretecek kavram yok") ve modal açılmaz.

## Veri Akışı

1. Kullanıcı bir giriş noktasından quiz başlatır → `quizConcept` set edilir, modal açılır.
2. Modal `POST /quiz/generate {concept_name, num_questions: 4}` çağırır, yüklenirken
   iskelet gösterir.
3. Soru 1/N gösterilir → şık seçilince anında doğru/yanlış renklendirmesi (glow) +
   açıklama gösterilir, şıklar kilitlenir.
4. "Sonraki Soru" ile ilerlenir; son soru sonrası skor (`doğru/toplam`) hesaplanır ve
   `POST /quiz/submit {concept_name, score}` çağırılır.
5. Skor ekranı gösterilir, "Kapat" ile modal kapanır, `fetchGraph()` tetiklenir.

## Hata Yönetimi

| Durum | Kullanıcıya gösterilen |
|---|---|
| `404` kavram bulunamadı | Mesaj + "Kapat" |
| `422` kaynak yok | Mesaj + "Kapat" |
| `502` üretim başarısız | Mesaj + "Tekrar Dene" (force_new olmadan yeniden generate) |
| Ağ hatası | "Sunucuya ulaşılamadı" |
| `submit` başarısız | Skor yine gösterilir, hata sessizce loglanır, nazik bir not: "sonuç kaydedilemedi" |

## Test Planı

Projede pytest altyapısı yok (ayrı bir backlog maddesi, bu spec'in kapsamı dışında).
Mevcut konvansiyon: `check_edges.py` / `check_status.py` gibi elle çalıştırılan doğrulama
scriptleri. Aynı desende `backend/check_studied.py` eklenir — quiz submit sonrası
`(User)-[:STUDIED]->(Concept)` ilişkisinin doğru yazıldığını Neo4j sorgusuyla doğrular.

Frontend: otomatik test yok, gerçek uygulama çalıştırılıp tarayıcıda uçtan uca denenerek
doğrulanır (mevcut proje konvansiyonu).

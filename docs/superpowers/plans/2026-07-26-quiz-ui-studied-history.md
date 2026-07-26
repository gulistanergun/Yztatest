# Quiz Arayüzü + STUDIED Geçmişi Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kullanıcının bir kavram için quiz çözebileceği bir arayüz eklemek (mevcut backend `/quiz/generate` + `/quiz/submit` üzerine) ve her quiz sonucunun `(User)-[:STUDIED]->(Concept)` ilişkisi olarak Neo4j'e kaydedilmesini sağlamak.

**Architecture:** Backend'de tek bir Cypher ekleme (mevcut `update_concept_after_quiz` fonksiyonunun içine, aynı transaction'da). Frontend'de yeni bağımsız bir `QuizModal.jsx` bileşeni + `NodeDetailsPanel.jsx`'e "Quiz Çöz" butonu + `App.jsx` header'ına "Bugünün Quizi" butonu.

**Tech Stack:** FastAPI + Neo4j (backend, değişmedi), React 19 + Vite (frontend, değişmedi), mevcut CSS custom property sistemi (`frontend/src/index.css`). Yeni bağımlılık yok.

## Global Constraints

- Login/kayıt ekranı YOK — `User` node tamamen arka planda, sabit `id: 'local_user'`.
- STUDIED sadece `/quiz/submit` çağrıldığında yazılır (kavram çıkarımı akışına dokunulmaz).
- Tüm kullanıcıya görünen metinler Türkçe.
- Backend `--port 8080` üzerinde çalışır (frontend kodu bu portu hardcode eder), `--host 127.0.0.1`.
- Yeni bir renk paleti/font icat edilmez — mevcut CSS custom property'ler (`--gece`, `--kor`, `--nane`, `--tehlike`, `--panel`, `--cizgi`, `--font-display`, `--font-body`, `--font-mono`) kullanılır.
- Doğru cevap `--nane` (mint) rengiyle glow, yanlış cevap `--tehlike` (kırmızı) rengiyle glow gösterir — bkz. spec'teki imza öğe kararı.
- Projede pytest/vitest altyapısı yok; bu plan yeni test çatısı kurmaz. Backend doğrulaması mevcut `check_*.py` script konvansiyonuyla, frontend doğrulaması gerçek tarayıcıda uçtan uca test ile yapılır.
- Git: sadece local commit, **push yok**. Commit mesajlarında hiçbir AI/Claude atfı bulunmaz (düz commit mesajı).
- Spec: `docs/superpowers/specs/2026-07-26-quiz-ui-studied-history-design.md`

---

### Task 1: Backend — STUDIED ilişkisi yazımı

**Files:**
- Modify: `backend/app/services/graph_service.py:267-334` (fonksiyon `update_concept_after_quiz`)
- Create: `backend/check_studied.py`

**Interfaces:**
- Consumes: Mevcut `POST /api/v1/quiz/submit` endpoint'i (`backend/app/routers/graph.py:81-93`), `GraphService.update_concept_after_quiz(concept_name: str, score: float) -> dict` imzası **değişmiyor**.
- Produces: Yeni Neo4j yan etkisi — `(User {id:'local_user'})-[:STUDIED {first_studied, attempts, last_score, last_studied}]->(Concept {name})`. Sonraki hiçbir task bu fonksiyonun dönüş değerine bağımlı değil (frontend zaten mevcut `new_stability`/`new_retrievability` alanlarını kullanıyor, onlar değişmiyor).

- [ ] **Step 1: Doğrulama scriptini yaz (once önce - "red" durumunu görmek için)**

`backend/check_studied.py` dosyasını oluştur:

```python
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    print("=" * 50)
    print("STUDIED ILISKILERI")
    print("=" * 50)
    r1 = session.run("MATCH ()-[r:STUDIED]->() RETURN count(r) AS total")
    for rec in r1:
        print(f"Toplam STUDIED iliskisi: {rec['total']}")

    print()
    print("SON 10 STUDIED KAYDI")
    print("=" * 50)
    r2 = session.run("""
        MATCH (u:User)-[r:STUDIED]->(c:Concept)
        RETURN u.id AS user_id, c.name AS concept, r.attempts AS attempts,
               r.last_score AS last_score, r.last_studied AS last_studied
        ORDER BY r.last_studied DESC
        LIMIT 10
    """)
    for rec in r2:
        print(f"  {rec['user_id']} -> {rec['concept']} | deneme: {rec['attempts']} | "
              f"son skor: {rec['last_score']} | son tarih: {rec['last_studied']}")

driver.close()
print()
print("Kontrol tamamlandi!")
```

- [ ] **Step 2: Scripti çalıştır, "red" durumunu doğrula**

Run (backend klasöründe, venv aktifken):
```bash
cd backend && ./.venv/Scripts/python.exe check_studied.py
```
Expected: `Toplam STUDIED iliskisi: 0` (henüz kod eklenmedi, hiç STUDIED yok).

- [ ] **Step 3: `update_concept_after_quiz` içine STUDIED yazımını ekle**

`backend/app/services/graph_service.py` dosyasında, mevcut şu blok (satır 304-320):

```python
            # 3. Veritabanını güncelle
            await session.run(
                """
                MATCH (c:Concept {name: $name})
                SET c.fsrs_d = $new_d,
                    c.fsrs_s = $new_s,
                    c.fsrs_p = $new_p,
                    c.last_studied = datetime() - duration({seconds: $elapsed_seconds}),
                    c.last_reviewed_at = datetime(),
                    c.updated_at = datetime()
                """,
                name=concept_name,
                new_d=updated_state["difficulty"],
                new_s=updated_state["stability"],
                new_p=updated_state["retrievability"],
                elapsed_seconds=elapsed_seconds,
            )
```

Bunun hemen altına (hâlâ `async with self.neo4j.session() as session:` bloğunun içinde, `logger.info` satırından önce) şunu ekle:

```python

            # 4. STUDIED gecmisini guncelle (User -> Concept iliskisi)
            await session.run(
                """
                MERGE (u:User {id: 'local_user'})
                MERGE (u)-[r:STUDIED]->(c:Concept {name: $name})
                ON CREATE SET r.first_studied = datetime(), r.attempts = 1
                ON MATCH SET r.attempts = coalesce(r.attempts, 0) + 1
                SET r.last_score = $score, r.last_studied = datetime()
                """,
                name=concept_name,
                score=score,
            )
```

- [ ] **Step 4: Backend'i yeniden başlat**

Mevcut uvicorn sürecini durdur ve yeniden başlat (port 8080, `--host 127.0.0.1`):
```bash
cd backend && ./.venv/Scripts/uvicorn.exe app.main:app --host 127.0.0.1 --port 8080
```
Startup loglarında hata olmadığını doğrula (`Application startup complete.` satırı).

- [ ] **Step 5: Gerçek bir quiz submit çağrısıyla "green" durumunu üret**

Graf'ta gerçekten var olan bir kavram adı kullan (örn. daha önce görülen "Docker"):
```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/quiz/submit -H "Content-Type: application/json" -d "{\"concept_name\": \"Docker\", \"score\": 0.75}"
```
Expected: `{"status":"success","concept":"Docker","score":0.75,...}` JSON yanıtı (hata yok).

- [ ] **Step 6: Doğrulama scriptini tekrar çalıştır, "green" durumunu doğrula**

```bash
cd backend && ./.venv/Scripts/python.exe check_studied.py
```
Expected: `Toplam STUDIED iliskisi: 1` ve alt listede `local_user -> Docker | deneme: 1 | son skor: 0.75 | ...` satırı.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/graph_service.py backend/check_studied.py
git commit -m "feat(backend): quiz sonuclarini STUDIED iliskisi olarak Neo4j'e kaydet"
```

---

### Task 2: Frontend — Quiz arayüzü (bileşen + stil + kablolama)

**Files:**
- Create: `frontend/src/components/QuizModal.jsx`
- Modify: `frontend/src/index.css` (dosya sonuna yeni bölüm eklenir)
- Modify: `frontend/src/components/NodeDetailsPanel.jsx:1-27` (import + prop + buton)
- Modify: `frontend/src/App.jsx` (state, handler'lar, header butonu, `QuizModal` render, `NodeDetailsPanel`'e prop geçişi)

**Interfaces:**
- Consumes: `POST /api/v1/quiz/generate {concept_name, num_questions, force_new}` → `{concept, topic, fsrs_p, questions: [{question, options, correct_index, explanation}], sources_used, from_bank, dropped_by_selfcheck}` (hata: 404/422/502). `POST /api/v1/quiz/submit {concept_name, score}` → `{status, concept, score, new_stability, new_retrievability}`. `GET /api/v1/quiz/recommendations?limit=1` → `{concepts: [{name, topic, fsrs_p, stability, source_count}], total}`.
- Produces: `QuizModal` bileşeni, props: `{ concept: string, onClose: () => void, onCompleted: () => void }`. `NodeDetailsPanel` yeni prop: `onStartQuiz: (label: string) => void`.

- [ ] **Step 1: `QuizModal.jsx` bileşenini oluştur**

`frontend/src/components/QuizModal.jsx`:

```jsx
import React, { useState, useEffect, useCallback } from 'react';
import { X, RotateCcw } from 'lucide-react';

const QuizModal = ({ concept, onClose, onCompleted }) => {
  const [status, setStatus] = useState('loading'); // loading | ready | error | finished
  const [errorInfo, setErrorInfo] = useState(null); // { message, canRetry }
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [revealed, setRevealed] = useState(false);
  const [correctCount, setCorrectCount] = useState(0);
  const [submitState, setSubmitState] = useState(null); // null | 'submitting' | 'submitted' | 'submit_failed'
  const [newRetention, setNewRetention] = useState(null);

  const fetchQuiz = useCallback(async (forceNew) => {
    setStatus('loading');
    setErrorInfo(null);
    try {
      const response = await fetch('http://127.0.0.1:8080/api/v1/quiz/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concept_name: concept, num_questions: 4, force_new: forceNew }),
      });
      if (!response.ok) {
        if (response.status === 404) {
          setErrorInfo({ message: 'Bu kavram bulunamadı.', canRetry: false });
        } else if (response.status === 422) {
          setErrorInfo({ message: 'Bu kavram için yeterli kaynak yok, quiz üretilemedi.', canRetry: false });
        } else if (response.status === 502) {
          setErrorInfo({ message: 'Soru üretimi başarısız oldu.', canRetry: true });
        } else {
          setErrorInfo({ message: 'Beklenmeyen bir hata oluştu.', canRetry: true });
        }
        setStatus('error');
        return;
      }
      const data = await response.json();
      setQuestions(data.questions || []);
      setCurrentIndex(0);
      setSelectedOption(null);
      setRevealed(false);
      setCorrectCount(0);
      setStatus('ready');
    } catch (error) {
      console.error('Quiz yuklenemedi:', error);
      setErrorInfo({ message: 'Sunucuya ulaşılamadı.', canRetry: true });
      setStatus('error');
    }
  }, [concept]);

  useEffect(() => {
    fetchQuiz(false);
  }, [fetchQuiz]);

  const currentQuestion = questions[currentIndex];
  const isLastQuestion = currentIndex === questions.length - 1;

  const handleSelect = (optionIndex) => {
    if (revealed) return;
    setSelectedOption(optionIndex);
    setRevealed(true);
    if (optionIndex === currentQuestion.correct_index) {
      setCorrectCount((prev) => prev + 1);
    }
  };

  const submitScore = async (finalCorrectCount) => {
    setSubmitState('submitting');
    const score = finalCorrectCount / questions.length;
    try {
      const response = await fetch('http://127.0.0.1:8080/api/v1/quiz/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concept_name: concept, score }),
      });
      if (!response.ok) {
        setSubmitState('submit_failed');
        return;
      }
      const data = await response.json();
      setNewRetention(typeof data.new_retrievability === 'number' ? data.new_retrievability : null);
      setSubmitState('submitted');
    } catch (error) {
      console.error('Quiz sonucu gonderilemedi:', error);
      setSubmitState('submit_failed');
    }
  };

  const handleNext = () => {
    if (isLastQuestion) {
      setStatus('finished');
      submitScore(correctCount);
      return;
    }
    setCurrentIndex((prev) => prev + 1);
    setSelectedOption(null);
    setRevealed(false);
  };

  const handleClose = () => {
    if (status === 'finished' && onCompleted) onCompleted();
    onClose();
  };

  return (
    <div className="quiz-overlay" onClick={handleClose}>
      <div className="quiz-card glass-panel" onClick={(e) => e.stopPropagation()}>
        <div className="quiz-card-header">
          <h3 className="quiz-title">{concept}</h3>
          <button onClick={handleClose} className="close-btn" aria-label="Kapat">
            <X size={20} />
          </button>
        </div>

        {status === 'loading' && (
          <div className="quiz-body quiz-loading">
            <div className="quiz-spinner" />
            <p>Sorular hazırlanıyor...</p>
          </div>
        )}

        {status === 'error' && errorInfo && (
          <div className="quiz-body quiz-error">
            <p>{errorInfo.message}</p>
            <div style={{ display: 'flex', gap: '8px' }}>
              {errorInfo.canRetry && (
                <button onClick={() => fetchQuiz(true)} className="quiz-btn quiz-btn-primary">
                  <RotateCcw size={14} /> Tekrar Dene
                </button>
              )}
              <button onClick={handleClose} className="quiz-btn">Kapat</button>
            </div>
          </div>
        )}

        {status === 'ready' && currentQuestion && (
          <div className="quiz-body">
            <span className="quiz-progress">{currentIndex + 1}/{questions.length}</span>
            <p className="quiz-question">{currentQuestion.question}</p>
            <div className="quiz-options">
              {currentQuestion.options.map((option, idx) => {
                let optionClass = 'quiz-option';
                if (revealed) {
                  if (idx === currentQuestion.correct_index) optionClass += ' quiz-option-correct';
                  else if (idx === selectedOption) optionClass += ' quiz-option-wrong';
                }
                return (
                  <button
                    key={idx}
                    className={optionClass}
                    onClick={() => handleSelect(idx)}
                    disabled={revealed}
                  >
                    {option}
                  </button>
                );
              })}
            </div>
            {revealed && (
              <div className="quiz-explanation">
                <p>{currentQuestion.explanation}</p>
                <button onClick={handleNext} className="quiz-btn quiz-btn-primary">
                  {isLastQuestion ? 'Sonucu Gör' : 'Sonraki Soru'}
                </button>
              </div>
            )}
          </div>
        )}

        {status === 'finished' && (
          <div className="quiz-body quiz-score">
            <p className="quiz-score-value">{correctCount}/{questions.length} doğru</p>
            {submitState === 'submitting' && <p className="text-sm text-muted">Sonuç kaydediliyor...</p>}
            {submitState === 'submitted' && newRetention !== null && (
              <p className="text-sm text-muted">Güncel hatırlama durumu: %{Math.round(newRetention * 100)}</p>
            )}
            {submitState === 'submit_failed' && (
              <p className="text-sm text-muted">Sonuç kaydedilemedi, ama quiz tamamlandı.</p>
            )}
            <button onClick={handleClose} className="quiz-btn quiz-btn-primary">Kapat</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default QuizModal;
```

- [ ] **Step 2: Quiz stillerini `index.css`'e ekle**

`frontend/src/index.css` dosyasının **sonuna** ekle:

```css
/* ---------- Quiz Modali ---------- */
.quiz-overlay {
  position: fixed;
  inset: 0;
  background: rgba(4, 8, 18, 0.72);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  animation: quizFadeIn 0.25s ease;
}

@keyframes quizFadeIn {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

.quiz-card {
  width: 100%;
  max-width: 520px;
  max-height: 80vh;
  overflow-y: auto;
  padding: 28px;
  animation: quizCardIn 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes quizCardIn {
  0% { opacity: 0; transform: translateY(18px) scale(0.98); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}

.quiz-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.quiz-title {
  font-family: var(--font-display);
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--kagit);
}

.quiz-body { display: flex; flex-direction: column; gap: 14px; }

.quiz-loading { align-items: center; text-align: center; padding: 32px 0; color: var(--sis); }

.quiz-spinner {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 3px solid var(--cizgi);
  border-top-color: var(--kor);
  animation: quizSpin 0.8s linear infinite;
  margin: 0 auto 12px;
}

@keyframes quizSpin { to { transform: rotate(360deg); } }

.quiz-progress {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--sis);
  letter-spacing: 0.05em;
}

.quiz-question {
  font-size: 1.05rem;
  line-height: 1.5;
  color: var(--kagit);
}

.quiz-options { display: flex; flex-direction: column; gap: 10px; }

.quiz-option {
  text-align: left;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--cizgi);
  background: rgba(255, 255, 255, 0.03);
  color: var(--kagit);
  font-family: var(--font-body);
  font-size: 0.92rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.25s;
}

.quiz-option:hover:not(:disabled) {
  border-color: var(--panel-cizgi);
  background: rgba(255, 180, 84, 0.06);
}

.quiz-option:disabled { cursor: default; }

.quiz-option-correct {
  border-color: var(--nane);
  background: rgba(110, 231, 216, 0.1);
  box-shadow: 0 0 0 1px rgba(110, 231, 216, 0.4), 0 0 18px rgba(110, 231, 216, 0.35);
}

.quiz-option-wrong {
  border-color: var(--tehlike);
  background: rgba(255, 107, 107, 0.1);
  box-shadow: 0 0 0 1px rgba(255, 107, 107, 0.4), 0 0 18px rgba(255, 107, 107, 0.25);
}

.quiz-explanation {
  padding-top: 6px;
  border-top: 1px solid var(--cizgi);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.quiz-explanation p { font-size: 0.85rem; color: var(--sis); line-height: 1.5; }

.quiz-btn {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.06);
  color: var(--sis);
  border: 1px solid var(--cizgi);
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.quiz-btn-primary {
  background: rgba(255, 180, 84, 0.14);
  color: var(--kor);
  border-color: rgba(255, 180, 84, 0.3);
}

.quiz-score { align-items: center; text-align: center; padding: 12px 0; }

.quiz-score-value {
  font-family: var(--font-display);
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--kor);
}
```

- [ ] **Step 3: `NodeDetailsPanel.jsx`'e "Quiz Çöz" butonunu ekle**

`frontend/src/components/NodeDetailsPanel.jsx` satır 1-2'yi değiştir:

Eskisi:
```jsx
import React from 'react';
import { X, Network, Compass } from 'lucide-react';
```

Yenisi:
```jsx
import React from 'react';
import { X, Network, Compass, Brain } from 'lucide-react';
```

Satır 10'u değiştir:

Eskisi:
```jsx
const NodeDetailsPanel = ({ node, onClose, onShowPath, learningPath, onClearPath, goalResult, onClearGoal }) => {
```

Yenisi:
```jsx
const NodeDetailsPanel = ({ node, onClose, onShowPath, learningPath, onClearPath, goalResult, onClearGoal, onStartQuiz }) => {
```

Satır 26-52 arasındaki `{canShowPath && (...)}` bloğunun içindeki buton kısmını değiştir:

Eskisi:
```jsx
      {canShowPath && (
        <div className="info-group">
          {!pathForThisNode ? (
            <button
              onClick={() => onShowPath(node.label)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                background: 'rgba(255,180,84,0.12)', color: 'var(--kor)',
                border: '1px solid rgba(255,180,84,0.3)', borderRadius: '6px',
                padding: '6px 12px', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
              }}
            >
              <Compass size={14} /> Bu Kavrama Giden Yolu Göster
            </button>
          ) : (
            <button
              onClick={onClearPath}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                background: 'rgba(255,255,255,0.06)', color: 'var(--sis)',
                border: '1px solid var(--cizgi)', borderRadius: '6px',
                padding: '6px 12px', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
              }}
            >
              <X size={14} /> Yolu Kapat
            </button>
          )}
```

Yenisi:
```jsx
      {canShowPath && (
        <div className="info-group">
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={() => onStartQuiz(node.label)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                background: 'rgba(110,231,216,0.12)', color: 'var(--nane)',
                border: '1px solid rgba(110,231,216,0.3)', borderRadius: '6px',
                padding: '6px 12px', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
              }}
            >
              <Brain size={14} /> Quiz Çöz
            </button>
            {!pathForThisNode ? (
              <button
                onClick={() => onShowPath(node.label)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  background: 'rgba(255,180,84,0.12)', color: 'var(--kor)',
                  border: '1px solid rgba(255,180,84,0.3)', borderRadius: '6px',
                  padding: '6px 12px', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
                }}
              >
                <Compass size={14} /> Bu Kavrama Giden Yolu Göster
              </button>
            ) : (
              <button
                onClick={onClearPath}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  background: 'rgba(255,255,255,0.06)', color: 'var(--sis)',
                  border: '1px solid var(--cizgi)', borderRadius: '6px',
                  padding: '6px 12px', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
                }}
              >
                <X size={14} /> Yolu Kapat
              </button>
            )}
          </div>
```

(Bloğun geri kalanı — `{pathForThisNode && !pathForThisNode.found && (...)}` ve `{pathForThisNode && pathForThisNode.found && (...)}` — aynen kalır, sadece yukarıdaki iç `<div>` kapanışını doğru yerde kapat.)

- [ ] **Step 4: `App.jsx`'e state, handler'lar ve header butonunu ekle**

`frontend/src/App.jsx` satır 1-5'i değiştir:

Eskisi:
```jsx
import React, { useState, useEffect, useRef } from 'react';
import MindMap from './components/MindMap';
import NodeDetailsPanel from './components/NodeDetailsPanel';
import Sidebar from './components/Sidebar';
import ChatBar from './components/ChatBar';
```

Yenisi:
```jsx
import React, { useState, useEffect, useRef } from 'react';
import MindMap from './components/MindMap';
import NodeDetailsPanel from './components/NodeDetailsPanel';
import Sidebar from './components/Sidebar';
import ChatBar from './components/ChatBar';
import QuizModal from './components/QuizModal';
```

Satır 19-20 civarına (state tanımlarının olduğu bloğa, `goalInputValue` state'inden hemen sonra) ekle:

Eskisi:
```jsx
  const [goalInputOpen, setGoalInputOpen] = useState(false);
  const [goalInputValue, setGoalInputValue] = useState('');
```

Yenisi:
```jsx
  const [goalInputOpen, setGoalInputOpen] = useState(false);
  const [goalInputValue, setGoalInputValue] = useState('');
  const [quizConcept, setQuizConcept] = useState(null);
```

`handleClearGoal` fonksiyonunun hemen altına (satır 188 civarı) ekle:

Eskisi:
```jsx
  const handleClearPath = () => setLearningPath(null);
  const handleClearGoal = () => setGoalResult(null);
```

Yenisi:
```jsx
  const handleClearPath = () => setLearningPath(null);
  const handleClearGoal = () => setGoalResult(null);

  const handleStartQuiz = (conceptName) => {
    setQuizConcept(conceptName);
  };

  const handleStartTodayQuiz = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8080/api/v1/quiz/recommendations?limit=1');
      const data = await response.json();
      if (data.concepts && data.concepts.length > 0) {
        setQuizConcept(data.concepts[0].name);
      } else {
        alert('Henüz quiz üretecek kavram yok.');
      }
    } catch (error) {
      console.error('Quiz onerisi alinamadi:', error);
      alert('Sunucuya ulaşılamadı.');
    }
  };

  const handleQuizClose = () => setQuizConcept(null);
  const handleQuizCompleted = () => fetchGraph();
```

Header buton satırında (satır 578-583 civarı), "🎯 Yeni Hedef" butonundan hemen önce ekle:

Eskisi:
```jsx
            <button
              onClick={() => setGoalInputOpen(prev => !prev)}
              style={{ background: goalInputOpen ? '#10B981' : '#374151', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}
              title="Haritada henüz olmayan bir konu için öğrenme yolu iste">
              🎯 Yeni Hedef
            </button>
```

Yenisi:
```jsx
            <button
              onClick={handleStartTodayQuiz}
              style={{ background: '#374151', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}
              title="En riskli kavramla hemen bir quiz baslat">
              🎯 Bugünün Quizi
            </button>
            <button
              onClick={() => setGoalInputOpen(prev => !prev)}
              style={{ background: goalInputOpen ? '#10B981' : '#374151', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}
              title="Haritada henüz olmayan bir konu için öğrenme yolu iste">
              🎯 Yeni Hedef
            </button>
```

`<NodeDetailsPanel ... />` çağrısını (satır 655-663 civarı) değiştir:

Eskisi:
```jsx
      <NodeDetailsPanel
        node={selectedNode}
        onClose={() => setSelectedNode(null)}
        onShowPath={handleShowPath}
        learningPath={learningPath}
        onClearPath={handleClearPath}
        goalResult={goalResult}
        onClearGoal={handleClearGoal}
      />
```

Yenisi:
```jsx
      <NodeDetailsPanel
        node={selectedNode}
        onClose={() => setSelectedNode(null)}
        onShowPath={handleShowPath}
        learningPath={learningPath}
        onClearPath={handleClearPath}
        goalResult={goalResult}
        onClearGoal={handleClearGoal}
        onStartQuiz={handleStartQuiz}
      />

      {quizConcept && (
        <QuizModal
          concept={quizConcept}
          onClose={handleQuizClose}
          onCompleted={handleQuizCompleted}
        />
      )}
```

- [ ] **Step 5: Frontend'i (yeniden) başlat**

Vite dev server zaten çalışıyorsa HMR ile otomatik güncellenir; çalışmıyorsa:
```bash
cd frontend && npm run dev
```

- [ ] **Step 6: Tarayıcıda uçtan uca doğrula**

`http://localhost:5173` adresini aç (backend `:8080`'de ayakta olmalı):
1. Kaynağı olan bir kavrama tıkla (örn. "Docker") → sağ panelde **"Quiz Çöz"** butonu görünmeli.
2. Butona tıkla → ortada karartılmış arka planlı bir kart açılmalı, "Sorular hazırlanıyor..." yükleniyor durumu görünmeli, ardından soru + 4 şık gelmeli.
3. Bir şıkka tıkla → seçilen/doğru şık anında renklenmeli (doğruysa `--nane` yeşil glow, kullanıcının seçtiği yanlışsa `--tehlike` kırmızı glow) + açıklama metni + "Sonraki Soru" butonu çıkmalı.
4. Son soruya kadar ilerle → skor ekranı ("X/4 doğru") ve güncellenen hatırlama yüzdesi görünmeli.
5. "Kapat"a bas → modal kapanmalı ve haritadaki ilgili node'un rengi (fsrs_p güncellendiği için) yenilenmiş olmalı.
6. Header'daki **"🎯 Bugünün Quizi"** butonuna bas → hiçbir kavram seçili değilken de otomatik en riskli kavramla aynı modal açılmalı.
7. Tarayıcı konsolunda (F12) hata olmadığını doğrula.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/QuizModal.jsx frontend/src/index.css frontend/src/components/NodeDetailsPanel.jsx frontend/src/App.jsx
git commit -m "feat(frontend): quiz cozme arayuzu (adim adim soru karti + Bugunun Quizi girisi)"
```

---

## Self-Review Notu

- **Spec kapsama:** Spec'teki her karar (User modeli, STUDIED tetikleyicisi, giriş noktaları, akış, hata yönetimi, görsel yön) yukarıdaki iki task'ta karşılanıyor.
- **Placeholder taraması:** Yok — her adımda tam kod var.
- **Tip/isim tutarlılığı:** `QuizModal` prop'ları (`concept`, `onClose`, `onCompleted`) Task 2 Step 1 ve Step 4'te birebir aynı; `onStartQuiz` prop adı Step 3 ve Step 4'te birebir aynı; backend response alan adları (`new_retrievability`, `concepts[].name`) hem plan hem gerçek kod ile eşleşiyor (kaynak dosyalar okunarak doğrulandı).

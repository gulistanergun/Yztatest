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
  const [meta, setMeta] = useState(null); // { fsrs_p, difficulty_reason, own_sources_count, from_bank }

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
      setMeta({
        fsrs_p: data.fsrs_p,
        difficultyReason: data.difficulty_reason,
        ownSourcesCount: data.own_sources_count,
        fromBank: data.from_bank,
      });
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
            {meta && currentIndex === 0 && (
              <div className="quiz-why">
                <span className="quiz-why-title">🧠 Neden bu soru?</span>
                <p className="quiz-why-text">{meta.difficultyReason}</p>
                <div className="quiz-why-tags">
                  {typeof meta.fsrs_p === 'number' && (
                    <span className="quiz-why-tag">Hatırlama: %{Math.round(meta.fsrs_p * 100)}</span>
                  )}
                  <span className="quiz-why-tag">
                    {meta.fromBank ? 'Soru bankasından' : 'Yeni üretildi'} · {meta.ownSourcesCount || 0} kendi kaynağından
                  </span>
                </div>
              </div>
            )}
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

import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

const scoreClass = (score) => {
  if (score >= 0.8) return 'history-score-good';
  if (score >= 0.5) return 'history-score-mid';
  return 'history-score-bad';
};

const HistoryPanel = ({ onClose }) => {
  const [status, setStatus] = useState('loading'); // loading | ready | error
  const [items, setItems] = useState([]);
  const [conceptFilter, setConceptFilter] = useState('all');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch('http://127.0.0.1:8080/api/v1/quiz/history?limit=50');
        if (!response.ok) throw new Error('history fetch failed');
        const data = await response.json();
        if (!cancelled) {
          setItems(data.history || []);
          setStatus('ready');
        }
      } catch (error) {
        console.error('Quiz gecmisi yuklenemedi:', error);
        if (!cancelled) setStatus('error');
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const uniqueConcepts = React.useMemo(
    () => Array.from(new Set(items.map((it) => it.concept))).sort((a, b) => a.localeCompare(b, 'tr')),
    [items]
  );

  const filteredItems = conceptFilter === 'all'
    ? items
    : items.filter((it) => it.concept === conceptFilter);

  return (
    <div className="quiz-overlay" onClick={onClose}>
      <div className="quiz-card history-card glass-panel" onClick={(e) => e.stopPropagation()}>
        <div className="quiz-card-header">
          <h3 className="quiz-title">📜 Quiz Geçmişi</h3>
          <button onClick={onClose} className="close-btn" aria-label="Kapat">
            <X size={20} />
          </button>
        </div>

        {status === 'loading' && (
          <div className="quiz-body quiz-loading">
            <div className="quiz-spinner" />
            <p>Geçmiş yükleniyor...</p>
          </div>
        )}

        {status === 'error' && (
          <div className="quiz-body quiz-error">
            <p>Geçmiş yüklenemedi. Sunucuya ulaşılamadı.</p>
          </div>
        )}

        {status === 'ready' && items.length === 0 && (
          <div className="quiz-body">
            <p className="text-sm text-muted">
              Henüz çözülmüş bir quiz yok. "Bugünün Quizi" ile başlayabilirsin.
            </p>
          </div>
        )}

        {status === 'ready' && items.length > 0 && (
          <>
            <select
              className="history-filter"
              value={conceptFilter}
              onChange={(e) => setConceptFilter(e.target.value)}
            >
              <option value="all">Tüm kavramlar</option>
              {uniqueConcepts.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>

            {filteredItems.length === 0 ? (
              <p className="text-sm text-muted" style={{ marginTop: '10px' }}>
                Bu kavram için kayıt yok.
              </p>
            ) : (
              <div className="history-list">
                {filteredItems.map((item) => (
                  <div key={item.id} className="history-item">
                    <div className="history-item-main">
                      <span className="history-concept">{item.concept}</span>
                      <span className="history-date">
                        {item.timestamp
                          ? new Date(item.timestamp).toLocaleString('tr-TR', {
                              day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                            })
                          : ''}
                      </span>
                    </div>
                    <div className="history-item-side">
                      <span className={`history-score ${scoreClass(item.score)}`}>
                        %{Math.round(item.score * 100)}
                      </span>
                      {typeof item.new_retrievability === 'number' && (
                        <span className="history-retention">
                          Hatırlama → %{Math.round(item.new_retrievability * 100)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default HistoryPanel;

import React from 'react';
import { X, Network, Compass, Brain } from 'lucide-react';
import RetentionSparkline from './RetentionSparkline';

const HEALTH_BADGE_CLASS = {
  strong: 'badge-baslangic',
  warning: 'badge-orta',
  critical: 'badge-ileri',
};

const NodeDetailsPanel = ({ node, onClose, onShowPath, learningPath, onClearPath, goalResult, onClearGoal, onStartQuiz }) => {
  if (!node) return null;
  const p = node.fsrs_p ?? 1.0;
  const canShowPath = !node.isCluster && !node.isVirtual;
  const pathForThisNode = learningPath && learningPath.target === node.label ? learningPath : null;
  const isGoalNode = node.isVirtual && goalResult && goalResult.target === node.label;

  return (
    <div className={`side-panel glass-panel ${node ? 'open' : ''}`}>
      <div className="panel-header">
        <h2 className="panel-title">{node.label}</h2>
        <button onClick={onClose} className="close-btn" aria-label="Kapat">
          <X size={24} />
        </button>
      </div>

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

          {pathForThisNode && !pathForThisNode.found && (
            <p className="text-sm text-muted" style={{ marginTop: '8px' }}>
              {pathForThisNode.reason}
            </p>
          )}

          {pathForThisNode && pathForThisNode.found && (
            <div style={{ marginTop: '10px' }}>
              <span className="info-label">
                Öğrenme Yolu ({pathForThisNode.source} → {pathForThisNode.target})
              </span>
              <ul className="related-list" style={{ marginTop: '6px' }}>
                {pathForThisNode.path.map((step, idx) => (
                  <li key={idx} className="related-item" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                    <span>{idx + 1}. {step.name}</span>
                    <span className={`badge ${HEALTH_BADGE_CLASS[step.health] || ''}`} style={{ fontSize: '11px' }}>
                      {step.health === 'strong' ? 'sağlam'
                        : step.health === 'warning' ? 'kritik eşik'
                        : step.health === 'critical' ? 'zayıf durak'
                        : 'bilinmiyor'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {isGoalNode && (
        <div className="info-group">
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
            <button
              onClick={onClearGoal}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                background: 'rgba(255,255,255,0.06)', color: 'var(--sis)',
                border: '1px solid var(--cizgi)', borderRadius: '6px',
                padding: '6px 12px', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
              }}
            >
              <X size={14} /> Kapat
            </button>
          </div>
          <p style={{ lineHeight: '1.6', fontSize: '14px' }}>{goalResult.message}</p>
          {goalResult.prerequisites.length > 0 && (
            <ul className="related-list" style={{ marginTop: '10px' }}>
              {goalResult.prerequisites.map((prereq, idx) => (
                <li key={idx} className="related-item" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                  <span>{prereq.name}</span>
                  <span
                    className={`badge ${HEALTH_BADGE_CLASS[prereq.health] || ''}`}
                    style={!HEALTH_BADGE_CLASS[prereq.health] ? { background: 'rgba(255,255,255,0.06)', color: 'var(--sis)', border: '1px solid var(--cizgi)' } : undefined}
                  >
                    {prereq.health === 'strong' ? 'sağlam'
                      : prereq.health === 'warning' ? 'kritik eşik'
                      : prereq.health === 'critical' ? 'zayıf durak'
                      : 'hiç çalışılmamış'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {!isGoalNode && (
      <div className="info-group">
        <span className="info-label">Kategori</span>
        <span className="info-value">{node.topic || 'Genel'}</span>
      </div>
      )}

      {!isGoalNode && typeof node.fsrs_p === 'number' && (
        <div className="info-group">
          <span className="info-label">Hatırlama Durumu</span>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span
              className={`badge ${p >= 0.8 ? 'badge-baslangic' : p >= 0.5 ? 'badge-orta' : 'badge-ileri'}`}
              title="FSRS modelinin tahmini hatırlama olasılığı"
            >
              %{Math.round(p * 100)}
              {p < 0.5 ? ' — tekrar gerekli' : p < 0.8 ? ' — kritik eşik' : ' — sağlam'}
            </span>
            {typeof node.stability === 'number' && (
              <span className="badge" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--sis)', border: '1px solid var(--cizgi)' }}>
                Stabilite: {node.stability.toFixed(1)} gün
              </span>
            )}
          </div>
          <div style={{ marginTop: '8px', height: '6px', borderRadius: '3px', background: 'rgba(255, 255, 255, 0.08)' }}>
            <div style={{
              width: `${p * 100}%`,
              height: '100%',
              borderRadius: '3px',
              background: p >= 0.8 ? 'var(--nane)' : p >= 0.5 ? 'var(--kor)' : 'var(--tehlike)',
              transition: 'width 0.5s ease',
            }} />
          </div>
          {canShowPath && (
            <div style={{ marginTop: '10px' }}>
              <span className="info-label" style={{ fontSize: '11px' }}>Hatırlama Geçmişi</span>
              <RetentionSparkline concept={node.label} />
            </div>
          )}
        </div>
      )}

      {!isGoalNode && (
      <div className="info-group">
        <span className="info-label">Zorluk</span>
        <div>
          <span className={`badge badge-${node.difficulty?.toLowerCase() || 'baslangic'}`}>
            {node.difficulty || 'Bilinmiyor'}
          </span>
        </div>
      </div>
      )}

      {node.created_at && (
        <div className="info-group">
          <span className="info-label">Öğrenilme Tarihi</span>
          <span className="info-value text-sm text-muted">
            {new Date(node.created_at).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })}
          </span>
        </div>
      )}

      {node.source_interactions && node.source_interactions.length > 0 && (
        <div className="info-group">
          <span className="info-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            Araştırma Konuları (Cevabı görmek için tıklayın)
          </span>
          <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {node.source_interactions.map((interaction, idx) => (
              <details key={idx} style={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.05)', 
                borderRadius: '6px', 
                padding: '8px',
                fontSize: '0.8rem',
                lineHeight: '1.4',
                cursor: 'pointer'
              }}>
                <summary style={{
                  color: 'var(--kor)',
                  outline: 'none',
                  fontWeight: 600
                }}>
                  {interaction.title}
                </summary>
                <div style={{ 
                  marginTop: '10px', 
                  paddingTop: '10px', 
                  borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#e0e0e0',
                  maxHeight: '250px',
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                  cursor: 'text'
                }}>
                  {interaction.answer ? interaction.answer : <span style={{opacity:0.5, fontStyle:'italic'}}>Bu sohbet için yapay zeka cevabı kaydedilmemiş.</span>}
                </div>
              </details>
            ))}
          </div>
        </div>
      )}

      {node.sources && node.sources.length > 0 && (
        <div className="info-group">
          <span className="info-label">Kaynak Linkleri</span>
          <ul className="related-list">
            {node.sources.map((url, idx) => (
              <li key={idx} className="related-item" style={{ fontSize: '0.8rem', padding: '6px' }}>
                <a href={url} target="_blank" rel="noreferrer" style={{ color: 'var(--kor)', textDecoration: 'none' }}>
                  {url.length > 30 ? url.substring(0, 30) + '...' : url}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {node.related_concepts && node.related_concepts.length > 0 && (
        <div className="info-group" style={{ marginTop: '16px' }}>
          <span className="info-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Network size={14} />
            İlişkili Kavramlar
          </span>
          <ul className="related-list">
            {node.related_concepts.map((rel, idx) => (
              <li key={idx} className="related-item">
                {rel}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default NodeDetailsPanel;

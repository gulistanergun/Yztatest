import React from 'react';
import { X, ExternalLink, Network } from 'lucide-react';

const NodeDetailsPanel = ({ node, onClose }) => {
  if (!node) return null;

  return (
    <div className={`side-panel glass-panel ${node ? 'open' : ''}`}>
      <div className="panel-header">
        <h2 className="panel-title">{node.label}</h2>
        <button onClick={onClose} className="close-btn" aria-label="Kapat">
          <X size={24} />
        </button>
      </div>

      <div className="info-group">
        <span className="info-label">Kategori</span>
        <span className="info-value">{node.topic || 'Genel'}</span>
      </div>

      <div className="info-group">
        <span className="info-label">Zorluk</span>
        <div>
          <span className={`badge badge-${node.difficulty?.toLowerCase() || 'baslangic'}`}>
            {node.difficulty || 'Bilinmiyor'}
          </span>
        </div>
      </div>

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
                  color: '#bb86fc', 
                  outline: 'none',
                  fontWeight: 'bold'
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
                <a href={url} target="_blank" rel="noreferrer" style={{ color: '#bb86fc', textDecoration: 'none' }}>
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

import React, { useState } from 'react';
import { Search, Sparkles, X, BrainCircuit, BookOpen } from 'lucide-react';

const ChatBar = ({ onSearch }) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    // Arama fonksiyonu için query'yi App.jsx'e gönder (node odaklaması için)
    onSearch(query.trim());

    // RAG Chat API Çağrısı
    setLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8080/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setResponse({ answer: `Hata oluştu: ${data.detail || 'Bilinmeyen Hata'}` });
      } else {
        setResponse(data);
      }
    } catch (error) {
      console.error("Chat error:", error);
      setResponse({ answer: "Bağlantı hatası oluştu. Hafızaya ulaşılamıyor." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chatbar-container">
      {/* Cevap Balonu (Glassmorphism Modal) */}
      {(loading || response) && (
        <div className="chat-response-modal glass-panel">
          <button 
            className="close-btn" 
            onClick={() => setResponse(null)}
            style={{ position: 'absolute', right: '15px', top: '15px', background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px', color: 'var(--kor)' }}>
            <BrainCircuit size={22} />
            <h3 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: '1.05rem' }}>İkinci beynin yanıtlıyor</h3>
          </div>

          {loading ? (
            <div className="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          ) : (
            <div className="chat-answer">
              <p style={{ lineHeight: '1.6', fontSize: '15px' }}>{response?.answer}</p>
              
              {response?.sources?.length > 0 && (
                <div style={{ marginTop: '20px', padding: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                  <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '0 0 10px 0', fontSize: '13px', color: '#9ca3af' }}>
                    <BookOpen size={14} /> Faydalanılan Kaynaklar
                  </h4>
                  <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#d1d5db' }}>
                    {response.sources.map((s, idx) => (
                      <li key={idx} style={{ marginBottom: '5px' }}>
                        <strong>{s.platform}</strong> 
                        {s.concepts.length > 0 && ` (${s.concepts.join(', ')})`}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <form className="chatbar glass-panel" onSubmit={handleSubmit}>
        <div className="chatbar-input-wrapper">
          <Search size={20} className="chat-icon text-muted" />
          <input 
            type="text" 
            placeholder="Zihninde ara veya soru sor (Örn: Docker nedir?)..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="chatbar-input"
          />
          <button type="submit" className="chat-submit-btn" disabled={loading}>
            <Sparkles size={18} className={loading ? 'pulse-anim' : ''} />
          </button>
        </div>
      </form>
    </div>
  );
};

export default ChatBar;

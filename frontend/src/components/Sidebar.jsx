import React, { useEffect, useState } from 'react';
import { Video, MessageSquare, Trash2, Clock, ChevronDown, ChevronRight, Sparkles, Bot } from 'lucide-react';

const Sidebar = ({ onSourceSelect, onGraphRefresh }) => {
  const [groupedSources, setGroupedSources] = useState({});
  const [expandedGroups, setExpandedGroups] = useState({ 'Bugün': true, 'Dün': false, 'Bu Hafta': false, 'Daha Eski': false });
  const [loading, setLoading] = useState(true);

  const fetchSources = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8080/api/v1/sources');
      const data = await response.json();
      groupSourcesByDate(data);
    } catch (err) {
      console.error("Kaynaklar yuklenemedi", err);
    } finally {
      setLoading(false);
    }
  };

  const groupSourcesByDate = (sources) => {
    const groups = { 'Bugün': [], 'Dün': [], 'Bu Hafta': [], 'Daha Eski': [] };
    const now = new Date();
    
    sources.forEach(src => {
      if (!src.date) return;
      const d = new Date(src.date);
      const isSameDay = now.getFullYear() === d.getFullYear() && now.getMonth() === d.getMonth() && now.getDate() === d.getDate();
      
      const yesterday = new Date(now);
      yesterday.setDate(yesterday.getDate() - 1);
      const isYesterday = yesterday.getFullYear() === d.getFullYear() && yesterday.getMonth() === d.getMonth() && yesterday.getDate() === d.getDate();
      
      const diffTime = now - d;
      const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

      if (isSameDay) {
        groups['Bugün'].push(src);
      } else if (isYesterday) {
        groups['Dün'].push(src);
      } else if (diffDays <= 7) {
        groups['Bu Hafta'].push(src);
      } else {
        groups['Daha Eski'].push(src);
      }
    });

    setGroupedSources(groups);
  };

  useEffect(() => {
    fetchSources();
  }, []);

  const handleDelete = async (e, sessionId) => {
    e.stopPropagation();
    if (!window.confirm("Bu kaynağı ve ona bağlı olan tüm kavramları silmek istediğine emin misin?")) return;

    try {
      const res = await fetch(`http://127.0.0.1:8080/api/v1/sources/${sessionId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        await fetchSources();
        if (onGraphRefresh) {
          onGraphRefresh();
        }
      }
    } catch (err) {
      console.error("Silme hatası:", err);
    }
  };

  const toggleGroup = (groupName) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupName]: !prev[groupName]
    }));
  };

  // Renkleri çıkarıp daha soft/mat tonlar kullanıyoruz ki göz yormasın
  const getPlatformDetails = (platform) => {
    const p = platform ? platform.toLowerCase() : '';
    if (p.includes('youtube')) return { icon: <Video size={14} />, label: 'YouTube' };
    if (p.includes('gemini')) return { icon: <Sparkles size={14} />, label: 'Gemini' };
    if (p.includes('chatgpt')) return { icon: <Bot size={14} />, label: 'ChatGPT' };
    return { icon: <MessageSquare size={14} />, label: platform || 'Web' };
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  };
  
  const formatDateForOlder = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' });
  };

  return (
    <div className="sidebar glass-panel">
      <div className="sidebar-header">
        <h2 className="title-glow" style={{ fontSize: '1.2rem' }}>Öğrenme Kaynakları</h2>
      </div>
      <div className="source-list" style={{ overflowY: 'auto', paddingRight: '5px' }}>
        {loading ? (
          <p className="loading-text">Yükleniyor...</p>
        ) : (
          Object.entries(groupedSources).map(([groupName, items]) => {
            if (items.length === 0) return null;
            const isExpanded = expandedGroups[groupName];
            return (
              <div key={groupName} style={{ marginBottom: '15px' }}>
                <div 
                  onClick={() => toggleGroup(groupName)}
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    cursor: 'pointer',
                    color: '#e0e0e0', // Daha mat bir başlık rengi
                    padding: '5px 10px', 
                    margin: '0 0 10px 0',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                  }}
                >
                  {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  <h3 style={{ 
                    fontSize: '0.8rem', 
                    margin: '0 0 0 5px',
                    textTransform: 'uppercase',
                    letterSpacing: '1px',
                    flex: 1
                  }}>
                    {groupName} <span style={{ opacity: 0.5, fontSize: '0.7rem' }}>({items.length})</span>
                  </h3>
                </div>
                
                {isExpanded && items.map((src) => {
                  const platformDetails = getPlatformDetails(src.platform);
                  return (
                    <div 
                      key={src.id} 
                      className="source-item"
                      onClick={() => onSourceSelect(src)}
                    >
                      <div className="source-icon" style={{ opacity: 0.6 }}>
                        {platformDetails.icon}
                      </div>
                      <div className="source-content" style={{ flex: 1, paddingRight: '10px' }}>
                        <p className="source-title" title={src.title}>{src.title}</p>
                        <span className="source-date" style={{ display: 'flex', alignItems: 'center', gap: '8px', opacity: 0.5 }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            {platformDetails.label}
                          </span>
                          <span>|</span>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={10} /> 
                            {groupName === 'Daha Eski' 
                              ? `${formatDateForOlder(src.date)} - ${formatTime(src.date)}` 
                              : formatTime(src.date)
                            }
                          </span>
                        </span>
                      </div>
                      <button 
                        className="delete-source-btn" 
                        onClick={(e) => handleDelete(e, src.id)}
                        title="Kaynağı Sil"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  );
                })}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default Sidebar;

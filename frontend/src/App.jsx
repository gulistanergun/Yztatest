import React, { useState, useEffect, useRef } from 'react';
import MindMap from './components/MindMap';
import NodeDetailsPanel from './components/NodeDetailsPanel';
import Sidebar from './components/Sidebar';
import ChatBar from './components/ChatBar';

function App() {
  const [fullGraphData, setFullGraphData] = useState({ nodes: [], edges: [] });
  const [displayGraph, setDisplayGraph] = useState({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSource, setActiveSource] = useState(null);
  
  // Dosya seçici için referans
  const fileInputRef = useRef(null);

  const fetchGraph = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8080/api/v1/graph');
      const data = await response.json();
      setFullGraphData(data);
      setDisplayGraph(data);
    } catch (error) {
      console.error("Zihin haritasi yuklenemedi:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, []);

  const handleSourceSelect = (source) => {
    setActiveSource(source);
    const filteredNodes = fullGraphData.nodes.filter(n => 
      n.sources && n.sources.some(url => url.includes(source.url))
    );
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredEdges = fullGraphData.edges.filter(e => 
      nodeIds.has(e.source) && nodeIds.has(e.target)
    );
    setDisplayGraph({ nodes: filteredNodes, edges: filteredEdges });
  };

  const handleSearch = (query) => {
    const term = query.toLowerCase();
    const foundNode = displayGraph.nodes.find(n => n.label.toLowerCase().includes(term));
    if (foundNode) {
      setSelectedNode(foundNode);
    }
  };

  const handleReset = () => {
    setActiveSource(null);
    setDisplayGraph(fullGraphData);
  };

  // ---- YENİ: JSON DIŞA AKTAR ----
  const handleExport = () => {
    if (fullGraphData.nodes.length === 0) {
      alert("Dışa aktarılacak veri yok!");
      return;
    }
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(fullGraphData, null, 2));
    const downloadNode = document.createElement('a');
    downloadNode.setAttribute("href", dataStr);
    downloadNode.setAttribute("download", `learnsphere_backup_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadNode);
    downloadNode.click();
    downloadNode.remove();
  };

  // ---- YENİ: JSON İÇE AKTAR ----
  const handleImport = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const importedData = JSON.parse(e.target.result);
        
        const response = await fetch('http://127.0.0.1:8080/api/v1/graph/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(importedData)
        });

        if (response.ok) {
          alert("Öğrenme ağı başarıyla içe aktarıldı!");
          fetchGraph(); // Ağı yenile
        } else {
          alert("İçe aktarma sırasında sunucu hatası oluştu.");
        }
      } catch (error) {
        console.error("İçe aktarma hatası:", error);
        alert("Dosya formatı hatalı. Lütfen geçerli bir yedek yükleyin.");
      }
    };
    reader.readAsText(file);
    // Aynı dosyayı tekrar seçebilmek için input'u sıfırla
    event.target.value = null; 
  };

  const stats = React.useMemo(() => {
    const now = Date.now();
    const hasP = fullGraphData.nodes.some((n) => typeof n.fsrs_p === 'number');
    let fresh = 0;   
    let cooling = 0; 
    for (const n of fullGraphData.nodes) {
      if (hasP) {
        if (typeof n.fsrs_p !== 'number') continue;
        if (n.fsrs_p >= 0.8) fresh++;
        else if (n.fsrs_p < 0.5) cooling++;
      } else {
        if (!n.created_at) continue;
        const ageH = (now - new Date(n.created_at).getTime()) / 36e5;
        if (ageH < 24) fresh++;
        else if (ageH > 72) cooling++;
      }
    }
    return { total: fullGraphData.nodes.length, fresh, cooling, hasP };
  }, [fullGraphData]);

  return (
    <div className="app-container notebook-layout">
      <Sidebar onSourceSelect={handleSourceSelect} onGraphRefresh={fetchGraph} />

      <div className="main-content">
        <div className="header glass-panel" style={{ padding: '18px 24px', margin: '24px', width: 'max-content', position: 'absolute', zIndex: 10 }}>
          <h1 className="title-glow" style={{ cursor: 'pointer' }} onClick={handleReset} title="Tüm ağa dön">
            Living Mind Tree<span className="spark">.</span>
          </h1>
          
          {/* YENİ: İçe/Dışa Aktar Butonları */}
          <div style={{ display: 'flex', gap: '10px', marginTop: '12px', marginBottom: '8px' }}>
            <button 
              onClick={handleExport} 
              style={{ background: '#374151', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
              📥 Dışa Aktar
            </button>
            <button 
              onClick={() => fileInputRef.current.click()} 
              style={{ background: '#374151', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
              📤 İçe Aktar
            </button>
            <input type="file" accept=".json" style={{ display: 'none' }} ref={fileInputRef} onChange={handleImport} />
          </div>

          <div className="statbar">
            <span className="stat"><b>{stats.total}</b> kavram</span>
            <span className="dot" />
            <span className={stats.hasP ? 'stat strong' : 'stat warm'}>
              <b>{stats.fresh}</b> {stats.hasP ? 'sağlam' : 'taze köz'}
            </span>
            <span className="dot" />
            <span className={stats.hasP ? 'stat risk' : 'stat cold'}>
              <b>{stats.cooling}</b> {stats.hasP ? 'riskte' : 'soğuyor'}
            </span>
          </div>
          {activeSource && (
            <p className="filter-note">
              Filtre: {activeSource.title}
              <button onClick={handleReset}>tümüne dön</button>
            </p>
          )}
        </div>

        <div className="graph-wrapper" style={{ flex: 1, position: 'relative' }}>
          {!loading && displayGraph.nodes.length > 0 && (
            <MindMap
              data={displayGraph}
              onNodeClick={(node) => setSelectedNode(node)}
            />
          )}
          {!loading && displayGraph.nodes.length === 0 && (
            <div className="empty-state">
              <h3>Zihin haritan henüz boş</h3>
              <p>
                ChatGPT, Gemini veya YouTube&apos;da öğrenmeye başla — eklenti kavramları arka planda toplayıp burada közlere dönüştürecek.
              </p>
            </div>
          )}
        </div>

        <ChatBar onSearch={handleSearch} />
      </div>

      <NodeDetailsPanel 
        node={selectedNode} 
        onClose={() => setSelectedNode(null)} 
      />
    </div>
  );
}

export default App;
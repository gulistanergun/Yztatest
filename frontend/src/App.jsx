import React, { useState, useEffect } from 'react';
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
    // Kaynağa göre filtrele
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

  // Durum çubuğu istatistikleri: hatırlama olasılığı (p) varsa onu, yoksa yaşı kullan
  const stats = React.useMemo(() => {
    const now = Date.now();
    const hasP = fullGraphData.nodes.some((n) => typeof n.fsrs_p === 'number');
    let fresh = 0;   // p >= 0.8 (sağlam)  | yaş < 24s (taze)
    let cooling = 0; // p < 0.5 (riskte)   | yaş > 72s (soğuyor)
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
      {/* Sol Panel: Kaynaklar */}
      <Sidebar onSourceSelect={handleSourceSelect} onGraphRefresh={fetchGraph} />

      <div className="main-content">
        <div className="header glass-panel" style={{ padding: '18px 24px', margin: '24px', width: 'max-content', position: 'absolute', zIndex: 10 }}>
          <h1 className="title-glow" style={{ cursor: 'pointer' }} onClick={handleReset} title="Tüm ağa dön">
            Living Mind Tree<span className="spark">.</span>
          </h1>
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

        {/* Merkez Graf */}
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
                ChatGPT, Gemini veya YouTube&apos;da öğrenmeye başla — eklenti
                kavramları arka planda toplayıp burada közlere dönüştürecek.
              </p>
            </div>
          )}
        </div>

        {/* Alt Panel: RAG Chat */}
        <ChatBar onSearch={handleSearch} />
      </div>

      {/* Sağ Panel: Node Detayları (Absolute over the canvas) */}
      <NodeDetailsPanel 
        node={selectedNode} 
        onClose={() => setSelectedNode(null)} 
      />
    </div>
  );
}

export default App;

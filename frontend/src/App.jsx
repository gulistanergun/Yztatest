import React, { useState, useEffect, useRef } from 'react';
import MindMap from './components/MindMap';
import NodeDetailsPanel from './components/NodeDetailsPanel';
import Sidebar from './components/Sidebar';
import ChatBar from './components/ChatBar';
import QuizModal from './components/QuizModal';
import HistoryPanel from './components/HistoryPanel';
import BrainHealthBadge from './components/BrainHealthBadge';

function App() {
  const [fullGraphData, setFullGraphData] = useState({ nodes: [], edges: [] });
  const [displayGraph, setDisplayGraph] = useState({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSource, setActiveSource] = useState(null);
  const [expandedClusters, setExpandedClusters] = useState(new Set());
  const [zoomToFitTrigger, setZoomToFitTrigger] = useState(0);
  const [focusCluster, setFocusCluster] = useState(null);
  const [isClusteringMode, setIsClusteringMode] = useState(false);
  const [learningPath, setLearningPath] = useState(null);
  const [goalResult, setGoalResult] = useState(null);
  const [goalInputOpen, setGoalInputOpen] = useState(false);
  const [goalInputValue, setGoalInputValue] = useState('');
  const [quizConcept, setQuizConcept] = useState(null);
  const [quizQueue, setQuizQueue] = useState([]);
  const quizJustCompletedRef = useRef(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const [pendingHistoryFile, setPendingHistoryFile] = useState(null);
  const [historyLimit, setHistoryLimit] = useState(50);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [importAllHistory, setImportAllHistory] = useState(false);

  // Brain Health Score state
  const [brainHealth, setBrainHealth] = useState(null);
  const [brainHealthLoading, setBrainHealthLoading] = useState(false);
  const [brainHealthError, setBrainHealthError] = useState(null);

  const fileInputRef = useRef(null);
  const chatHistoryInputRef = useRef(null);
  const clusterNodesRef = useRef({});

  const fetchGraph = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8080/api/v1/graph');
      const data = await response.json();
      setFullGraphData(data);
    } catch (error) {
      console.error("Zihin haritasi yuklenemedi:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchBrainHealth = async () => {
    setBrainHealthLoading(true);
    setBrainHealthError(null);
    try {
      const response = await fetch('http://127.0.0.1:8080/api/v1/brain-health');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setBrainHealth(data);
    } catch (error) {
      console.error('Beyin sağlığı skoru yüklenemedi:', error);
      setBrainHealthError('Skor yüklenemedi');
    } finally {
      setBrainHealthLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
    fetchBrainHealth();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const quizParam = params.get('quiz');
    if (quizParam) {
      handleStartQuiz(quizParam);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  const handleSourceSelect = (source) => {
    setActiveSource(source);
    setZoomToFitTrigger(prev => prev + 1);
  };

  const handleSearch = (query) => {
    const term = query.toLowerCase();
    const foundNode = fullGraphData.nodes.find(n => n.label.toLowerCase().includes(term));
    if (foundNode) {
      const cid = foundNode.cluster_id || 'Genel';
      setExpandedClusters(prev => {
        const next = new Set(prev);
        next.add(cid);
        return next;
      });
      const parentClusterNode = fullGraphData.nodes.find(n => n.id === cid);
      if (parentClusterNode) {
          setFocusCluster(parentClusterNode);
      }
      setTimeout(() => setSelectedNode(foundNode), 100);
    }
  };

  const handleReset = () => {
    setActiveSource(null);
    setExpandedClusters(new Set());
    setFocusCluster(null);
    setIsClusteringMode(false);
    setZoomToFitTrigger(prev => prev + 1);
  };

  const handleCollapseAll = () => {
    setExpandedClusters(new Set());
    setFocusCluster(null);
    setZoomToFitTrigger(prev => prev + 1);
  };

  const allClusters = React.useMemo(() => {
    const map = {};
    fullGraphData.nodes.forEach(n => {
      const cid = n.cluster_id || 'Genel';
      if (!map[cid]) map[cid] = { id: cid, count: 0, p_sum: 0, p_count: 0 };
      map[cid].count++;
      if (typeof n.fsrs_p === 'number') {
        map[cid].p_sum += n.fsrs_p;
        map[cid].p_count++;
      }
    });
    return Object.values(map).map(c => ({
      id: c.id,
      count: c.count,
      avg_p: c.p_count > 0 ? c.p_sum / c.p_count : null
    })).sort((a, b) => b.count - a.count);
  }, [fullGraphData]);

  const handleClusterSelect = (clusterId) => {
    setIsClusteringMode(true);
    setFocusCluster({ id: clusterId, t: Date.now() });

    const ancestors = new Set([clusterId]);
    let currentId = clusterId;
    const visited = new Set();

    while (currentId) {
      if (visited.has(currentId)) break;
      visited.add(currentId);

      const node = fullGraphData.nodes.find(n => n.id === currentId);
      if (node && node.cluster_id && node.cluster_id !== 'Genel' && node.cluster_id !== currentId) {
        ancestors.add(node.cluster_id);
        currentId = node.cluster_id;
      } else {
        break;
      }
    }

    setExpandedClusters(ancestors);

    const selectedNodeObj = fullGraphData.nodes.find(n => n.id === clusterId);
    if (selectedNodeObj) {
      setSelectedNode(selectedNodeObj);
    } else if (clusterNodesRef.current[clusterId]) {
      setSelectedNode(clusterNodesRef.current[clusterId]);
    } else {
      setSelectedNode({ id: clusterId, label: clusterId, isVirtual: true });
    }
  };

  const expandAncestorsFor = (names) => {
    setExpandedClusters(prev => {
      const next = new Set(prev);
      names.forEach(name => {
        let currentId = name;
        const visited = new Set();
        while (currentId) {
          if (visited.has(currentId)) break;
          visited.add(currentId);
          const n = fullGraphData.nodes.find(nd => nd.id === currentId);
          if (n && n.cluster_id && n.cluster_id !== 'Genel' && n.cluster_id !== currentId) {
            next.add(n.cluster_id);
            currentId = n.cluster_id;
          } else {
            break;
          }
        }
      });
      return next;
    });
  };

  const handleShowPath = async (targetLabel) => {
    try {
      const response = await fetch(`http://127.0.0.1:8080/api/v1/learning-path?target=${encodeURIComponent(targetLabel)}`);
      if (!response.ok) {
        setLearningPath({ target: targetLabel, found: false, reason: 'Kavram bulunamadı.' });
        return;
      }
      const result = await response.json();
      setLearningPath(result);
      if (result.found) {
        expandAncestorsFor(result.path.map(step => step.name));
      }
    } catch (error) {
      console.error("Ogrenme yolu yuklenemedi:", error);
      setLearningPath({ target: targetLabel, found: false, reason: 'Sunucuya ulaşılamadı.' });
    }
  };

  const handleClearPath = () => setLearningPath(null);
  const handleClearGoal = () => setGoalResult(null);

  const handleStartQuiz = (conceptName) => {
    quizJustCompletedRef.current = false;
    setQuizQueue([]); 
    setQuizConcept(conceptName);
  };

  const handleStartTodayQuiz = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8080/api/v1/quiz/recommendations?limit=5');
      const data = await response.json();
      if (data.concepts && data.concepts.length > 0) {
        const names = data.concepts.map(c => c.name);
        setQuizQueue(names.slice(1));
        setQuizConcept(names[0]);
      } else {
        alert('Henüz quiz üretecek kavram yok.');
      }
    } catch (error) {
      console.error('Quiz onerisi alinamadi:', error);
      alert('Sunucuya ulaşılamadı.');
    }
  };

  const handleQuizCompleted = () => {
    quizJustCompletedRef.current = true;
    fetchGraph();
    fetchBrainHealth();
  };

  const handleQuizClose = () => {
    if (quizJustCompletedRef.current && quizQueue.length > 0) {
      quizJustCompletedRef.current = false;
      const [next, ...rest] = quizQueue;
      setQuizQueue(rest);
      setQuizConcept(next);
      return;
    }
    quizJustCompletedRef.current = false;
    setQuizQueue([]);
    setQuizConcept(null);
  };

  const handleResolveGoal = async (goalText) => {
    setLearningPath(null);
    setGoalResult({
      target: goalText, in_graph: false, prerequisites: [], weak_prerequisites: [],
      message: 'Aranıyor... (haritanda olmayan yeni bir konuysa birkaç saniye sürebilir)',
      loading: true,
    });
    setSelectedNode({ id: goalText, label: goalText, isVirtual: true });

    try {
      const response = await fetch('http://127.0.0.1:8080/api/v1/learning-goal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal: goalText }),
      });
      const data = await response.json();

      if (data.in_graph) {
        setGoalResult(null);
        setLearningPath(data);
        if (data.found) {
          expandAncestorsFor(data.path.map(step => step.name));
        }
        const node = fullGraphData.nodes.find(n => n.id === data.target);
        setSelectedNode(node || { id: data.target, label: data.target, isVirtual: true });
      } else {
        setLearningPath(null);
        setGoalResult(data);
        setSelectedNode({ id: data.target, label: data.target, isVirtual: true });
      }
    } catch (error) {
      console.error("Hedef cozumlenemedi:", error);
      setLearningPath(null);
      setGoalResult({
        target: goalText, in_graph: false, prerequisites: [], weak_prerequisites: [],
        message: 'Sunucuya ulaşılamadı.',
      });
      setSelectedNode({ id: goalText, label: goalText, isVirtual: true });
    }
  };

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
          fetchGraph(); 
        } else {
          alert("İçe aktarma sırasında sunucu hatası oluştu.");
        }
      } catch (error) {
        console.error("İçe aktarma hatası:", error);
        alert("Dosya formatı hatalı. Lütfen geçerli bir yedek yükleyin.");
      }
    };
    reader.readAsText(file);
    event.target.value = null;
  };

  const handleChatHistoryFileSelect = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    setPendingHistoryFile(file); 
    event.target.value = null; 
  };

  const confirmHistoryUpload = async () => {
    if (!pendingHistoryFile) return;

    const formData = new FormData();
    formData.append("file", pendingHistoryFile);
    formData.append("limit", importAllHistory ? 0 : historyLimit);

    try {
      setLoading(true);
      setPendingHistoryFile(null); 

      const response = await fetch('http://127.0.0.1:8080/api/v1/history/upload', {
        method: 'POST',
        body: formData
      });
      const result = await response.json();
      
      if (response.ok && result.status === "success") {
        alert(`${result.imported_count} adet sohbet geçmişi başarıyla aktarıldı! AutoProcessor haritanızı arka planda otomatik olarak oluşturacak.`);
      } else {
        alert("Hata: " + result.message);
      }
    } catch (err) {
      console.error("Geçmiş yükleme hatası:", err);
      alert("Dosya yüklenirken sunucuya ulaşılamadı.");
    } finally {
      setLoading(false);
    }
  };

  // YENİ: VERİTABANI SIFIRLAMA FONKSİYONU
  // YENİ: VERİTABANI SIFIRLAMA FONKSİYONU
  const handleClearDatabase = async () => {
    setShowResetConfirm(false); // Modalı kapat
    try {
      setLoading(true);
      const response = await fetch('http://127.0.0.1:8080/api/v1/graph/clear', {
        method: 'DELETE'
      });
      
      if (response.ok) {
        alert("Sistem başarıyla ilk günkü haline sıfırlandı!");
        window.location.reload(); 
      } else {
        alert("Sıfırlama sırasında sunucu hatası oluştu.");
      }
    } catch (error) {
      console.error("Sıfırlama hatası:", error);
      alert("Sıfırlama sırasında sunucuya ulaşılamadı.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedNode) return;
    if (learningPath) {
      const isTarget = learningPath.target === selectedNode.label;
      const isOnPath = learningPath.found && learningPath.path.some(step => step.name === selectedNode.label);
      if (!isTarget && !isOnPath) setLearningPath(null);
    }
    if (goalResult) {
      const isTarget = goalResult.target === selectedNode.label;
      const isPrereq = goalResult.prerequisites.some(p => p.name === selectedNode.label);
      if (!isTarget && !isPrereq) setGoalResult(null);
    }
  }, [selectedNode]);

  const highlightedPath = React.useMemo(() => {
    if (!learningPath || !learningPath.found) return null;
    const nodeIds = new Set(learningPath.path.map(s => s.name));
    const weakIds = new Set(learningPath.weak_stops);
    const edgeKeys = new Set();
    const names = learningPath.path.map(s => s.name);
    for (let i = 0; i < names.length - 1; i++) {
      const pair = [names[i], names[i + 1]].sort();
      edgeKeys.add(`${pair[0]}::${pair[1]}`);
    }
    return { nodeIds, weakIds, edgeKeys };
  }, [learningPath]);

  const goalHighlight = React.useMemo(() => {
    if (!goalResult) return null;
    const nodeIds = new Set(goalResult.prerequisites.map(p => p.name));
    const weakIds = new Set(goalResult.weak_prerequisites);
    return { nodeIds, weakIds, edgeKeys: new Set() };
  }, [goalResult]);

  useEffect(() => {
    if (!fullGraphData || !fullGraphData.nodes) return;

    let filteredNodes = fullGraphData.nodes;
    let filteredEdges = fullGraphData.edges;

    if (activeSource) {
      filteredNodes = fullGraphData.nodes.filter(n =>
        n.sources && n.sources.some(url => url.includes(activeSource.url))
      );
      const nodeIds = new Set(filteredNodes.map(n => n.id));
      filteredEdges = fullGraphData.edges.filter(e =>
        nodeIds.has(e.source?.id || e.source) && nodeIds.has(e.target?.id || e.target)
      );
    }

    if (!isClusteringMode) {
      const nodes = filteredNodes.map(n => ({
        ...n,
        isCluster: false,
        isExpandedHub: false
      }));
      const edges = filteredEdges.map(e => ({
        ...e,
        source: typeof e.source === 'object' ? e.source.id : e.source,
        target: typeof e.target === 'object' ? e.target.id : e.target,
        isHubEdge: false
      }));
      setDisplayGraph({ nodes, edges });
      return;
    }

    const nodes = [];
    const edges = [];
    const nodeMap = new Map();

    filteredNodes.forEach(n => {
      n.children = [];
      n.isCluster = false;
      n.isVirtual = false;
      nodeMap.set(n.id, n);
    });

    filteredNodes.forEach(n => {
      const cid = n.cluster_id;
      if (cid && cid !== 'Genel' && !nodeMap.has(cid)) {
        if (!clusterNodesRef.current[cid]) {
          clusterNodesRef.current[cid] = {
            id: cid,
            label: cid,
            cluster_id: 'Genel',
            isVirtual: true
          };
        }
        const vNode = clusterNodesRef.current[cid];
        vNode.children = [];
        vNode.isCluster = false;
        vNode.fsrs_p = undefined;
        nodeMap.set(cid, vNode);
      }
    });

    nodeMap.forEach(n => {
      const cid = n.cluster_id;
      if (cid && cid !== 'Genel' && cid !== n.id) {
        const parent = nodeMap.get(cid);
        if (parent) {
          parent.children.push(n);
          parent.isCluster = true;
        }
      }
    });

    const getHighestVisibleAncestor = (nodeId) => {
      let curr = nodeMap.get(nodeId);
      let lastVisible = curr;
      const visited = new Set();
      while (curr && curr.cluster_id && curr.cluster_id !== 'Genel') {
        if (curr.cluster_id === curr.id || visited.has(curr.id)) break;
        visited.add(curr.id);

        const parent = nodeMap.get(curr.cluster_id);
        if (!parent) break;
        if (!expandedClusters.has(parent.id)) {
          lastVisible = parent;
        }
        curr = parent;
      }
      return lastVisible;
    };

    const displayNodesMap = new Map();

    nodeMap.forEach(n => {
      const ancestor = getHighestVisibleAncestor(n.id);
      if (ancestor.id === n.id) {
        if (n.x === undefined && n.cluster_id && n.cluster_id !== 'Genel') {
          const parent = nodeMap.get(n.cluster_id);
          if (parent && parent.x !== undefined) {
            n.x = parent.x + (Math.random() - 0.5) * 10;
            n.y = parent.y + (Math.random() - 0.5) * 10;
          }
        }
        n.isExpandedHub = n.isCluster && expandedClusters.has(n.id);
        n.member_count = n.children.length;

        if (n.children.length > 0) {
          let sum = 0, count = 0;
          n.children.forEach(c => {
            if (typeof c.fsrs_p === 'number') { sum += c.fsrs_p; count++; }
          });
          if (count > 0 && n.fsrs_p === undefined) n.fsrs_p = sum / count;
        }

        displayNodesMap.set(n.id, n);

        if (n.isExpandedHub) {
          n.children.forEach(child => {
            const childAncestor = getHighestVisibleAncestor(child.id);
            if (childAncestor.id === child.id) {
              edges.push({ source: n.id, target: child.id, isHubEdge: true });
            }
          });
        }
      }
    });

    const edgeSet = new Set();
    filteredEdges.forEach(e => {
      const sid = typeof e.source === 'object' ? e.source.id : e.source;
      const tid = typeof e.target === 'object' ? e.target.id : e.target;

      const sNode = getHighestVisibleAncestor(sid);
      const tNode = getHighestVisibleAncestor(tid);

      if (sNode && tNode && sNode.id !== tNode.id) {
        const key1 = `${sNode.id}::${tNode.id}`;
        const key2 = `${tNode.id}::${sNode.id}`;
        if (!edgeSet.has(key1) && !edgeSet.has(key2)) {
          edgeSet.add(key1);
          edges.push({ ...e, source: sNode.id, target: tNode.id, isHubEdge: false });
        }
      }
    });

    setDisplayGraph({ nodes: Array.from(displayNodesMap.values()), edges });
  }, [fullGraphData, expandedClusters, activeSource, isClusteringMode]);

  const handleNodeClick = (node) => {
    if (node.isCluster) {
      setExpandedClusters(prev => {
        const next = new Set(prev);
        if (next.has(node.id)) {
          next.delete(node.id);
        } else {
          next.add(node.id);
        }
        return next;
      });
      setFocusCluster({ id: node.id, t: Date.now() });
    }
    setSelectedNode(node);
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
      <Sidebar
        data={fullGraphData}
        onSourceSelect={handleSourceSelect}
        activeSource={activeSource}
        clusters={allClusters}
        onClusterSelect={handleClusterSelect}
        isClusteringMode={isClusteringMode}
      />

      <div className="main-content">
        <div className="header glass-panel" style={{ padding: '18px 24px', margin: '24px', width: 'max-content', position: 'absolute', zIndex: 10 }}>
          <h1 className="title-glow" style={{ cursor: 'pointer' }} onClick={handleReset} title="Tüm ağa dön">
            Living Mind Tree<span className="spark">.</span>
          </h1>

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
            <button
              onClick={() => chatHistoryInputRef.current.click()}
              style={{ background: '#8B5CF6', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}
              title="ChatGPT (conversations.json) veya Gemini (MyActivity.json) dosyanızı yükleyerek haritayı ilk günden doldurun">
              🤖 Geçmişi Yükle
            </button>
            <input type="file" accept=".json" style={{ display: 'none' }} ref={chatHistoryInputRef} onChange={handleChatHistoryFileSelect} />
            <button
              onClick={() => {
                const nextMode = !isClusteringMode;
                setIsClusteringMode(nextMode);
                if (!nextMode) {
                  setExpandedClusters(new Set());
                  setFocusCluster(null);
                }
              }}
              style={{
                background: isClusteringMode ? '#10B981' : '#374151',
                color: 'white',
                border: 'none',
                padding: '6px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: '600'
              }}
              title="Zihin haritasını konularına göre gruplar"
            >
              Konu Kümeleme: {isClusteringMode ? 'Açık' : 'Kapalı'}
            </button>
            {isClusteringMode && expandedClusters.size > 0 && (
              <button
                onClick={handleCollapseAll}
                style={{ background: '#2563EB', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
                Kümeleri Daralt
              </button>
            )}
            <button
              onClick={handleStartTodayQuiz}
              style={{ background: '#374151', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}
              title="En riskli kavramla hemen bir quiz baslat">
              🎯 Bugünün Quizi
            </button>
            <button
              onClick={() => setHistoryOpen(true)}
              style={{ background: '#374151', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}
              title="Geçmişte çözülen quizlerin listesi">
              📜 Geçmiş
            </button>
            <button
              onClick={() => setGoalInputOpen(prev => !prev)}
              style={{ background: goalInputOpen ? '#10B981' : '#374151', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}
              title="Haritada henüz olmayan bir konu için öğrenme yolu iste">
              🎯 Yeni Hedef
            </button>
            {/* SIFIRLAMA BUTONU */}
            <button
              onClick={() => setShowResetConfirm(true)}
              style={{ background: '#ef4444', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}
              title="Tüm veritabanını ve haritayı temizle">
              🗑️ Sıfırla
            </button>
          </div>

          {goalInputOpen && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!goalInputValue.trim()) return;
                handleResolveGoal(goalInputValue.trim());
                setGoalInputValue('');
                setGoalInputOpen(false);
              }}
              style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}
            >
              <input
                type="text"
                autoFocus
                value={goalInputValue}
                onChange={(e) => setGoalInputValue(e.target.value)}
                placeholder="Ne öğrenmek istiyorsun? (örn. Büyük Dil Modelleri)"
                style={{ flex: 1, padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--cizgi)', background: 'rgba(255,255,255,0.06)', color: 'white', fontSize: '12px' }}
              />
              <button type="submit" style={{ background: '#10B981', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}>
                Rota Oluştur
              </button>
            </form>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <BrainHealthBadge
              data={brainHealth}
              loading={brainHealthLoading}
              error={brainHealthError}
            />
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
              onNodeClick={handleNodeClick}
              zoomToFitTrigger={zoomToFitTrigger}
              focusCluster={focusCluster}
              isClusteringMode={isClusteringMode}
              selectedNode={selectedNode}
              highlightedPath={highlightedPath || goalHighlight}
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
        onShowPath={handleShowPath}
        learningPath={learningPath}
        onClearPath={handleClearPath}
        goalResult={goalResult}
        onClearGoal={handleClearGoal}
        onStartQuiz={handleStartQuiz}
      />

      {quizConcept && (
        <>
          <QuizModal
            concept={quizConcept}
            onClose={handleQuizClose}
            onCompleted={handleQuizCompleted}
          />
          {quizQueue.length > 0 && (
            <div className="quiz-queue-badge">
              Bugünün Quizi — sırada {quizQueue.length} kavram daha var
            </div>
          )}
        </>
      )}

      {historyOpen && (
        <HistoryPanel onClose={() => setHistoryOpen(false)} />
      )}

      {pendingHistoryFile && (
        <div className="quiz-overlay" onClick={() => setPendingHistoryFile(null)} style={{zIndex: 9999, position: 'fixed', top:0, left:0, right:0, bottom:0, display:'flex', alignItems:'center', justifyContent:'center', backgroundColor: 'rgba(0,0,0,0.7)'}}>
          <div className="quiz-card glass-panel" onClick={(e) => e.stopPropagation()} style={{background: '#1f2937', color: 'white', padding: '24px', borderRadius: '12px', width: '100%', maxWidth: '500px'}}>
            <div className="quiz-card-header" style={{display: 'flex', justifyContent: 'space-between', marginBottom: '15px'}}>
              <h3 className="quiz-title" style={{margin:0, color: '#10B981'}}>Geçmişi İçe Aktar</h3>
              <button onClick={() => setPendingHistoryFile(null)} style={{background:'transparent', border:'none', color:'white', cursor:'pointer', fontSize:'16px'}}>✖</button>
            </div>
            <div className="quiz-body">
              <p style={{marginBottom: '20px', fontSize: '14px', color: '#D1D5DB'}}>
                Token maliyetlerini ve işlem süresini yönetmek için, dosyadan kaç adet geçmiş sohbetin analiz edileceğini seçin (En yeniler alınır).
              </p>
              
              <label style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '15px', cursor: 'pointer', fontSize: '14px'}}>
                <input 
                  type="checkbox" 
                  checked={importAllHistory} 
                  onChange={(e) => setImportAllHistory(e.target.checked)} 
                  style={{cursor: 'pointer'}}
                />
                Tüm geçmişi yükle (Dikkat: Yüksek token tüketebilir)
              </label>

              {!importAllHistory && (
                <div style={{display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px'}}>
                  <label style={{fontSize: '14px'}}>Aktarılacak Son Sohbet Sayısı:</label>
                  <input 
                    type="number" 
                    value={historyLimit} 
                    onChange={(e) => setHistoryLimit(parseInt(e.target.value) || 0)}
                    min="1"
                    style={{ padding: '10px', borderRadius: '6px', border: '1px solid #4B5563', background: 'rgba(255,255,255,0.06)', color: 'white', width: '100px' }}
                  />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button onClick={() => setPendingHistoryFile(null)} style={{ background: '#ef4444', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}>İptal</button>
                <button onClick={confirmHistoryUpload} style={{ background: '#10B981', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}>Onayla ve Yükle</button>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* YENİ: SIFIRLAMA İKİLİ ONAY MODALI */}
      {showResetConfirm && (
        <div className="quiz-overlay" onClick={() => setShowResetConfirm(false)} style={{zIndex: 9999, position: 'fixed', top:0, left:0, right:0, bottom:0, display:'flex', alignItems:'center', justifyContent:'center', backgroundColor: 'rgba(0,0,0,0.8)'}}>
          <div className="quiz-card glass-panel" onClick={(e) => e.stopPropagation()} style={{background: '#1f2937', color: 'white', padding: '30px', borderRadius: '12px', width: '100%', maxWidth: '450px', textAlign: 'center', borderTop: '4px solid #ef4444'}}>
            <h2 style={{margin: '0 0 15px 0', color: '#ef4444'}}>⚠️ Kritik Uyarı</h2>
            <p style={{marginBottom: '25px', fontSize: '16px', lineHeight: '1.5', color: '#D1D5DB'}}>
              Gerçekten LearnSphere AI sisteminde işlenen tüm verileri silmek istiyor musun?
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '15px' }}>
              <button 
                onClick={() => setShowResetConfirm(false)} 
                style={{ background: '#374151', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', flex: 1 }}>
                Hayır (Korunsun)
              </button>
              <button 
                onClick={handleClearDatabase} 
                style={{ background: '#ef4444', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', flex: 1 }}>
                Evet (Sıfırla)
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default App;
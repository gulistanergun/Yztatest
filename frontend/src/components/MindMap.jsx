import React, { useRef, useCallback, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const MindMap = ({ data, onNodeClick }) => {
  const graphRef = useRef();
  const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight });

  useEffect(() => {
    const handleResize = () => {
      setDimensions({ width: window.innerWidth, height: window.innerHeight });
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleNodeClick = useCallback(
    (node) => {
      // Düğüme yaklaş (zoom in)
      const distance = 40;
      const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z || 0);
      graphRef.current.centerAt(node.x, node.y, 1000);
      graphRef.current.zoom(8, 2000);
      
      if (onNodeClick) onNodeClick(node);
    },
    [onNodeClick]
  );

  // backend edges -> react-force-graph links
  const graphData = {
    nodes: data.nodes || [],
    links: data.edges || []
  };
  const getRetrievability = (node) => node?.fsrs_p ?? 1.0;

  return (
    <div className="graph-container">
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        nodeLabel="label"
        nodeColor={(node) => {
          const p = getRetrievability(node);
          return p >= 0.80 ? '#00e676' : p >= 0.50 ? '#ff9100' : '#ff1744';
        }}
        nodeRelSize={6}
        linkColor={(link) => {
          const sourceNode = graphData.nodes.find(n => n.id === link.source?.id || n.id === link.source);
          const targetNode = graphData.nodes.find(n => n.id === link.target?.id || n.id === link.target);
          
          const pSource = getRetrievability(sourceNode);
          const pTarget = getRetrievability(targetNode);
          const avgP = (pSource + pTarget) / 2;
          
          // Zayıflayan bağlar daha silik görünür
          const alpha = Math.max(0.05, avgP * 0.5);
          return `rgba(187, 134, 252, ${alpha})`;
        }}
        linkWidth={2}
        linkDirectionalParticles={(link) => {
          const sourceNode = graphData.nodes.find(n => n.id === link.source?.id || n.id === link.source);
          const targetNode = graphData.nodes.find(n => n.id === link.target?.id || n.id === link.target);
          const avgP = (getRetrievability(sourceNode) + getRetrievability(targetNode)) / 2;
          return avgP > 0.5 ? 2 : 0; // Çok unutulmuş bağlarda partikül hareketi dursun
        }}
        linkDirectionalParticleSpeed={0.005}
        onNodeClick={handleNodeClick}
        backgroundColor="transparent"
        // Düğüm çizimi (Glow efekti ve Unutma Eğrisi)
        nodeCanvasObject={(node, ctx, globalScale) => {
          const label = node.label;
          const fontSize = 12 / globalScale;
          
          // FSRS p bazlı renklendirme
          const p = getRetrievability(node);
          let fillStyle = '#00e676';
          let shadowColor = '#69f0ae';
          let shadowBlur = 20;
          let opacity = 1.0;
          
          if (p >= 0.80) {
            // Yeşil (Taze bilgi)
            fillStyle = '#00e676';
            shadowColor = '#69f0ae';
            shadowBlur = 20;
          } else if (p >= 0.50) {
            // Turuncu (Kritik eşik)
            fillStyle = '#ff9100';
            shadowColor = '#ffab40';
            shadowBlur = 12;
            opacity = 0.85;
          } else {
            // Kırmızı (Unutulmuş)
            fillStyle = '#ff1744';
            shadowColor = '#ff5252';
            shadowBlur = 8;
            opacity = 0.60;
          }
          
          ctx.globalAlpha = opacity;

          // Düğüm dairesi
          ctx.beginPath();
          ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI, false);
          ctx.fillStyle = fillStyle;
          ctx.shadowBlur = shadowBlur;
          ctx.shadowColor = shadowColor;
          ctx.fill();
          
          // Metin (Label)
          ctx.shadowBlur = 0;
          ctx.font = `${fontSize}px Sans-Serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`;
          ctx.fillText(label, node.x, node.y + 12);
          
          ctx.globalAlpha = 1; // Reset alpha
        }}
      />
    </div>
  );
};

export default MindMap;

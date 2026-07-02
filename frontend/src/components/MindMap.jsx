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

  return (
    <div className="graph-container">
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        nodeLabel="label"
        nodeColor={(node) => '#bb86fc'}
        nodeRelSize={6}
        linkColor={() => 'rgba(187, 134, 252, 0.4)'}
        linkWidth={2}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.005}
        onNodeClick={handleNodeClick}
        backgroundColor="transparent"
        // Düğüm çizimi (Glow efekti ve Node Decay)
        nodeCanvasObject={(node, ctx, globalScale) => {
          const label = node.label;
          const fontSize = 12 / globalScale;
          
          // Zaman hesaplaması (Node Decay)
          let fillStyle = '#8a2be2'; // default
          let shadowColor = '#bb86fc';
          let shadowBlur = 15;
          let opacity = 1;
          
          if (node.created_at) {
            const nodeDate = new Date(node.created_at);
            const now = new Date();
            const diffHours = Math.abs(now - nodeDate) / (1000 * 60 * 60);
            
            if (diffHours < 1) {
              // Son 1 saat (Yeni bilgi) - Çok parlak
              fillStyle = '#d500f9';
              shadowColor = '#e040fb';
              shadowBlur = 25;
            } else if (diffHours < 24) {
              // Son 24 saat (Normal bilgi)
              fillStyle = '#8a2be2';
              shadowColor = '#bb86fc';
              shadowBlur = 15;
            } else {
              // 24 saatten eski (Unutulmaya yüz tutmuş)
              fillStyle = '#4a3b69';
              shadowColor = 'transparent';
              shadowBlur = 0;
              opacity = 0.6;
            }
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

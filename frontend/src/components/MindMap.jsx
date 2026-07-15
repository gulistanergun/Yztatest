import React, { useRef, useCallback, useEffect, useState, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

// ---- "Köz" sıcaklık skalası ----
// Taze bilgi kor gibi sıcak parlar; unutulmaya yüz tutan bilgi küle soğur.
const EMBER = {
  blaze: { fill: '#FFD9A0', glow: '#FFB454', text: 'rgba(255, 231, 200, 0.95)' }, // < 1 saat
  warm:  { fill: '#FFB454', glow: '#C9803A', text: 'rgba(255, 220, 180, 0.9)'  }, // < 24 saat
  amber: { fill: '#C9803A', glow: 'rgba(201, 128, 58, 0.5)', text: 'rgba(226, 200, 170, 0.8)' }, // < 3 gün
  cool:  { fill: '#7E7568', glow: 'transparent', text: 'rgba(180, 186, 197, 0.65)' }, // < 1 hafta
  ash:   { fill: '#4C596E', glow: 'transparent', text: 'rgba(139, 152, 172, 0.5)'  }, // daha eski
};

function emberOf(createdAt) {
  if (!createdAt) return EMBER.amber;
  const ageH = (Date.now() - new Date(createdAt).getTime()) / 36e5;
  if (ageH < 1) return EMBER.blaze;
  if (ageH < 24) return EMBER.warm;
  if (ageH < 72) return EMBER.amber;
  if (ageH < 168) return EMBER.cool;
  return EMBER.ash;
}

// ---- Hatırlama olasılığı (FSRS/HLR p değeri) skalası ----
// Ekip kararı: p >= 0.80 güçlü, 0.50-0.80 kritik eşik, < 0.50 riskte.
// Renkler köz kimliğiyle harmanlandı: nane-yeşil / kehribar / kırmızı.
const RETENTION = {
  strong: { fill: '#57D9A3', glow: 'rgba(87, 217, 163, 0.55)', text: 'rgba(199, 240, 222, 0.95)' },
  mid:    { fill: '#FFB454', glow: 'rgba(255, 180, 84, 0.55)', text: 'rgba(255, 220, 180, 0.9)' },
  weak:   { fill: '#FF6B6B', glow: 'rgba(255, 107, 107, 0.6)', text: 'rgba(255, 200, 200, 0.9)' },
};

function styleOf(node) {
  // p değeri varsa hatırlama skalası; yoksa yaş bazlı köz skalasına düş
  const p = node.fsrs_p;
  if (typeof p === 'number') {
    if (p >= 0.8) return RETENTION.strong;
    if (p >= 0.5) return RETENTION.mid;
    return RETENTION.weak;
  }
  return emberOf(node.created_at);
}

function isAtRisk(node) {
  return typeof node.fsrs_p === 'number' && node.fsrs_p < 0.5;
}

function isFresh(createdAt) {
  if (!createdAt) return false;
  return (Date.now() - new Date(createdAt).getTime()) / 36e5 < 24;
}

const REDUCED_MOTION =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

const MindMap = ({ data, onNodeClick }) => {
  const graphRef = useRef();
  const containerRef = useRef();
  const hasAutoFitted = useRef(false);

  // Veri değişince (filtre vb.) haritayı yeniden çerçevele
  useEffect(() => {
    hasAutoFitted.current = false;
  }, [data]);
  const [dimensions, setDimensions] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  useEffect(() => {
    const measure = () => {
      const el = containerRef.current;
      if (el) {
        setDimensions({ width: el.clientWidth, height: el.clientHeight });
      }
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);

  // Bağlantı sayısı (degree): çok bağlanan kavram daha büyük köz olur
  const degree = useMemo(() => {
    const d = {};
    for (const e of data.edges || []) {
      d[e.source] = (d[e.source] || 0) + 1;
      d[e.target] = (d[e.target] || 0) + 1;
    }
    return d;
  }, [data]);

  const radiusOf = useCallback(
    (node) => 4 + Math.min(degree[node.id] || 0, 6) * 1.1,
    [degree]
  );

  const handleNodeClick = useCallback(
    (node) => {
      graphRef.current.centerAt(node.x, node.y, 800);
      graphRef.current.zoom(5, 1200);
      if (onNodeClick) onNodeClick(node);
    },
    [onNodeClick]
  );

  const graphData = {
    nodes: data.nodes || [],
    links: data.edges || [],
  };

  return (
    <div className="graph-container" ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        nodeLabel="label"
        nodeRelSize={6}
        linkColor={(link) => {
          // Edge soluklaştırma: bağ, iki ucun en ZAYIF hatırlama değerini taşır.
          // Bilgi bağları zayıfladıkça çizgiler silikleşir/kızarır.
          const ps = link.source?.fsrs_p;
          const pt = link.target?.fsrs_p;
          if (typeof ps === 'number' && typeof pt === 'number') {
            const pMin = Math.min(ps, pt);
            if (pMin < 0.5) return `rgba(255, 107, 107, ${0.10 + pMin * 0.3})`;
            if (pMin < 0.8) return `rgba(255, 180, 84, ${0.08 + pMin * 0.3})`;
            return 'rgba(87, 217, 163, 0.3)';
          }
          // p yoksa yaş bazlı eski davranış
          const warm =
            isFresh(link.source?.created_at) || isFresh(link.target?.created_at);
          return warm ? 'rgba(255, 180, 84, 0.35)' : 'rgba(139, 152, 172, 0.14)';
        }}
        linkWidth={1.2}
        linkDirectionalParticles={REDUCED_MOTION ? 0 : 1}
        linkDirectionalParticleSpeed={0.004}
        linkDirectionalParticleWidth={2}
        linkDirectionalParticleColor={() => 'rgba(255, 217, 160, 0.7)'}
        onNodeClick={handleNodeClick}
        onEngineStop={() => {
          if (!hasAutoFitted.current && graphRef.current) {
            graphRef.current.zoomToFit(600, 90);
            hasAutoFitted.current = true;
          }
        }}
        backgroundColor="transparent"
        nodeCanvasObject={(node, ctx, globalScale) => {
          // Fizik motoru ilk karede konum atamadan çizim yapma
          if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
          const ember = styleOf(node);
          const baseR = radiusOf(node);

          // Riskteki kavramlar (p < 0.5) dikkat çekmek için nefes alır;
          // p verisi yoksa eski davranış: taze közler nefes alır.
          let r = baseR;
          const shouldPulse = isAtRisk(node) ||
            (node.fsrs_p === undefined && isFresh(node.created_at));
          if (!REDUCED_MOTION && shouldPulse) {
            r = baseR + Math.sin(Date.now() / 600 + (node.index || 0)) * 0.8;
          }

          // Dış ısı halkası (sadece sıcak közlerde)
          if (ember.glow !== 'transparent') {
            const halo = ctx.createRadialGradient(node.x, node.y, r * 0.4, node.x, node.y, r * 3.2);
            halo.addColorStop(0, ember.glow + (ember.glow.startsWith('rgba') ? '' : '55'));
            halo.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.beginPath();
            ctx.arc(node.x, node.y, r * 3.2, 0, 2 * Math.PI, false);
            ctx.fillStyle = halo;
            ctx.fill();
          }

          // Köz çekirdeği
          ctx.beginPath();
          ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
          ctx.fillStyle = ember.fill;
          ctx.fill();

          // Sıcak közlerde parlak iç nokta
          if (ember === EMBER.blaze || ember === EMBER.warm) {
            ctx.beginPath();
            ctx.arc(node.x - r * 0.25, node.y - r * 0.25, r * 0.35, 0, 2 * Math.PI, false);
            ctx.fillStyle = 'rgba(255, 245, 225, 0.9)';
            ctx.fill();
          }

          // Etiket
          const fontSize = Math.max(11 / globalScale, 2.2);
          ctx.font = `500 ${fontSize}px 'IBM Plex Sans', sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillStyle = ember.text;
          ctx.fillText(node.label, node.x, node.y + r + 3);
        }}
        nodePointerAreaPaint={(node, color, ctx) => {
          if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
          ctx.beginPath();
          ctx.arc(node.x, node.y, radiusOf(node) + 6, 0, 2 * Math.PI, false);
          ctx.fillStyle = color;
          ctx.fill();
        }}
      />
    </div>
  );
};

export default MindMap;

import React, { useState, useEffect } from 'react';

const healthColorVar = (p) => {
  if (p >= 0.8) return 'var(--nane)';
  if (p >= 0.5) return 'var(--kor)';
  return 'var(--tehlike)';
};

// Kavramın geçmiş quiz denemelerindeki hatırlama olasılığını (retrievability)
// küçük bir eğri olarak gösterir. Tek seri olduğu için ayrı bir legend yok;
// bağlam "Hatırlama Geçmişi" başlığından geliyor. Ham veri (tarih/skor) her
// nokta üzerinde native <title> tooltip olarak, tam liste ise 📜 Geçmiş
// panelinde zaten mevcut (tablo görünümü karşılığı).
const RetentionSparkline = ({ concept }) => {
  const [points, setPoints] = useState(null); // null = yükleniyor, [] = veri yok

  useEffect(() => {
    let cancelled = false;
    setPoints(null);
    (async () => {
      try {
        const response = await fetch(
          `http://127.0.0.1:8080/api/v1/quiz/history?concept=${encodeURIComponent(concept)}&limit=20`
        );
        const data = await response.json();
        if (cancelled) return;
        const ordered = (data.history || [])
          .filter((h) => typeof h.new_retrievability === 'number')
          .slice()
          .reverse(); // backend en yeniden eskiye döner; grafikte eskiden yeniye akmalı
        setPoints(ordered);
      } catch (error) {
        console.error('Unutma eğrisi yüklenemedi:', error);
        if (!cancelled) setPoints([]);
      }
    })();
    return () => { cancelled = true; };
  }, [concept]);

  if (!points || points.length < 2) return null;

  const width = 240;
  const height = 56;
  const padX = 6;
  const padY = 10;
  const n = points.length;
  const xAt = (i) => padX + (i * (width - padX * 2)) / (n - 1);
  const yAt = (p) => padY + (1 - p) * (height - padY * 2);

  const linePath = points
    .map((pt, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i).toFixed(1)} ${yAt(pt.new_retrievability).toFixed(1)}`)
    .join(' ');

  const last = points[n - 1];
  const lastColor = healthColorVar(last.new_retrievability);

  return (
    <div className="sparkline-wrap">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Kavramın hatırlama geçmişi">
        <path
          d={linePath}
          fill="none"
          stroke="var(--sis)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.55"
        />
        {points.map((pt, i) => (
          <circle
            key={pt.id || i}
            cx={xAt(i)}
            cy={yAt(pt.new_retrievability)}
            r="10"
            fill="transparent"
          >
            <title>
              {pt.timestamp
                ? new Date(pt.timestamp).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' })
                : '?'}
              {' · %'}{Math.round(pt.score * 100)} skor{' · %'}{Math.round(pt.new_retrievability * 100)} hatırlama
            </title>
          </circle>
        ))}
        <circle
          cx={xAt(n - 1)}
          cy={yAt(last.new_retrievability)}
          r="4"
          fill={lastColor}
          stroke="var(--gece)"
          strokeWidth="2"
        />
      </svg>
      <div className="sparkline-caption">
        <span>{n} deneme</span>
        <span style={{ color: lastColor, fontWeight: 700 }}>%{Math.round(last.new_retrievability * 100)}</span>
      </div>
    </div>
  );
};

export default RetentionSparkline;

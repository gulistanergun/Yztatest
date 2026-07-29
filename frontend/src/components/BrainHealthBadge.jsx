import React, { useState, useEffect, useRef } from 'react';

/**
 * BrainHealthBadge — Beyin Sağlığı Skoru göstergesi.
 * Kompakt bir rozet olarak başlığın yanında durur.
 * Tıklanınca alt bileşen detaylarını (breakdown) açar.
 */

const SCORE_COLORS = {
  mukemmel: '#57D9A3',    // nane — mint green
  iyi:      '#6ee7d8',    // lighter mint
  orta:     '#FFB454',    // kor — amber
  zayif:    '#c9803a',    // kor-koyu — dark amber
  kritik:   '#FF6B6B',    // tehlike — coral red
  empty:    '#64748b',    // kul — slate gray
};

function getScoreColor(score) {
  if (score === null || score === undefined) return SCORE_COLORS.empty;
  if (score >= 85) return SCORE_COLORS.mukemmel;
  if (score >= 70) return SCORE_COLORS.iyi;
  if (score >= 50) return SCORE_COLORS.orta;
  if (score >= 25) return SCORE_COLORS.zayif;
  return SCORE_COLORS.kritik;
}

function CircularGauge({ score, size = 52, strokeWidth = 4.5 }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = score !== null && score !== undefined
    ? Math.max(0, Math.min(100, score)) / 100
    : 0;
  const offset = circumference * (1 - progress);
  const color = getScoreColor(score);

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="bhb-gauge"
    >
      {/* Track */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="rgba(139, 152, 172, 0.15)"
        strokeWidth={strokeWidth}
      />
      {/* Progress arc */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.8s ease, stroke 0.4s ease' }}
      />
      {/* Center text */}
      <text
        x={size / 2}
        y={size / 2}
        textAnchor="middle"
        dominantBaseline="central"
        fill={color}
        fontSize="13"
        fontWeight="700"
        fontFamily="var(--font-display)"
      >
        {score !== null && score !== undefined ? score : '—'}
      </text>
    </svg>
  );
}

function BreakdownRow({ label, value, unit, barColor, barPercent }) {
  return (
    <div className="bhb-breakdown-row">
      <span className="bhb-breakdown-label">{label}</span>
      <div className="bhb-breakdown-bar-wrap">
        <div
          className="bhb-breakdown-bar"
          style={{
            width: `${Math.max(0, Math.min(100, barPercent || 0))}%`,
            background: barColor,
            transition: 'width 0.6s ease',
          }}
        />
      </div>
      <span className="bhb-breakdown-value">
        {value !== null && value !== undefined ? `${value}${unit || ''}` : '—'}
      </span>
    </div>
  );
}

const BrainHealthBadge = ({ data, loading, error }) => {
  const [expanded, setExpanded] = useState(false);
  const panelRef = useRef(null);

  // Click-outside handler
  useEffect(() => {
    if (!expanded) return;
    const handleClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setExpanded(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [expanded]);

  // Loading state
  if (loading) {
    return (
      <div className="bhb-container">
        <div className="bhb-badge bhb-loading">
          <div className="bhb-pulse" />
          <span className="bhb-title">Beyin Sağlığı</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bhb-container">
        <div className="bhb-badge bhb-error" title={error}>
          <span className="bhb-title">Beyin Sağlığı</span>
          <span className="bhb-score-text" style={{ color: 'var(--tehlike)', fontSize: '0.7rem' }}>Hata</span>
        </div>
      </div>
    );
  }

  // Empty / no data state
  if (!data || data.score === null || data.score === undefined) {
    return (
      <div className="bhb-container" ref={panelRef}>
        <div
          className="bhb-badge bhb-empty"
          onClick={() => setExpanded((v) => !v)}
          title="Henüz skor oluşturmak için yeterli öğrenme verisi yok."
        >
          <CircularGauge score={null} size={40} strokeWidth={3.5} />
          <div className="bhb-text">
            <span className="bhb-title">Beyin Sağlığı</span>
            <span className="bhb-score-text" style={{ color: 'var(--kul)' }}>Veri yok</span>
          </div>
        </div>
        {expanded && (
          <div className="bhb-dropdown glass-panel">
            <p className="bhb-empty-msg">
              Henüz skor oluşturmak için yeterli öğrenme verisi yok.
            </p>
          </div>
        )}
      </div>
    );
  }

  const { score, label, breakdown, concept_summary } = data;
  const color = getScoreColor(score);
  const bd = breakdown || {};

  return (
    <div className="bhb-container" ref={panelRef}>
      {/* Compact badge */}
      <div
        className="bhb-badge"
        onClick={() => setExpanded((v) => !v)}
        title={`Beyin Sağlığı: ${score} / 100 — ${label}`}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setExpanded((v) => !v); }}
      >
        <CircularGauge score={score} />
        <div className="bhb-text">
          <span className="bhb-title">Beyin Sağlığı</span>
          <span className="bhb-score-text" style={{ color }}>
            {score} <span className="bhb-max">/ 100</span>
            <span className="bhb-label" style={{ background: `${color}18`, color }}>{label}</span>
          </span>
        </div>
        <span className={`bhb-chevron ${expanded ? 'bhb-chevron-up' : ''}`}>▾</span>
      </div>

      {/* Expandable breakdown panel */}
      {expanded && (
        <div className="bhb-dropdown glass-panel">
          <div className="bhb-dropdown-header">
            <span>Skor Detayları</span>
            <span className="bhb-dropdown-score" style={{ color }}>{score}/100</span>
          </div>

          <div className="bhb-breakdown-list">
            <BreakdownRow
              label="Ortalama Hatırlama"
              value={bd.average_retention?.value != null ? `%${Math.round(bd.average_retention.value)}` : null}
              barColor="#57D9A3"
              barPercent={bd.average_retention?.value}
            />
            <BreakdownRow
              label="Sağlam Kavram Oranı"
              value={bd.healthy_ratio?.value != null ? `%${Math.round(bd.healthy_ratio.value)}` : null}
              barColor="#6ee7d8"
              barPercent={bd.healthy_ratio?.value}
            />
            <BreakdownRow
              label="Son Quiz Başarısı"
              value={bd.recent_quiz_accuracy?.value != null ? `%${Math.round(bd.recent_quiz_accuracy.value)}` : null}
              barColor="#FFB454"
              barPercent={bd.recent_quiz_accuracy?.value ?? 0}
            />
            <BreakdownRow
              label="30 Günlük Düzenlilik"
              value={bd.study_consistency?.value != null ? `%${Math.round(bd.study_consistency.value)}` : null}
              barColor="#c9803a"
              barPercent={bd.study_consistency?.value}
            />
          </div>

          {concept_summary && (
            <div className="bhb-summary">
              <span className="bhb-summary-item">
                <b>{concept_summary.total}</b> kavram
              </span>
              <span className="bhb-summary-dot" />
              <span className="bhb-summary-item" style={{ color: '#57D9A3' }}>
                <b>{concept_summary.healthy}</b> sağlam
              </span>
              <span className="bhb-summary-dot" />
              <span className="bhb-summary-item" style={{ color: '#FFB454' }}>
                <b>{concept_summary.warning}</b> uyarı
              </span>
              <span className="bhb-summary-dot" />
              <span className="bhb-summary-item" style={{ color: '#FF6B6B' }}>
                <b>{concept_summary.at_risk}</b> riskte
              </span>
            </div>
          )}

          {bd.recent_quiz_accuracy?.value === null && (
            <p className="bhb-no-quiz-note">
              Henüz quiz çözülmediği için bu bileşen hariç tutuldu.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default BrainHealthBadge;

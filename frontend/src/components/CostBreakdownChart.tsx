import { useMemo, useState } from 'react';

export interface CostRun {
  id: string;
  name: string;
  color: string; // run-identity color (for the run legend / index label)
  points: {
    lcoe: number;
    wind: number;
    wave: number;
    kite: number;
    coaxial: number;
    transmission: number;
  }[];
}

interface CostBreakdownChartProps {
  runs: CostRun[];
  width?: number;
  height?: number;
}

const TECHS = [
  { key: 'wind', label: 'Wind', color: '#3b82f6' },
  { key: 'wave', label: 'WEC', color: '#f59e0b' },
  { key: 'kite', label: 'Kite', color: '#22c55e' },
  { key: 'coaxial', label: 'Coaxial', color: '#a855f7' },
  { key: 'transmission', label: 'Transmission', color: '#6b7280' },
] as const;

/**
 * Grouped + stacked annualized-cost chart. X = LCOE target; at each LCOE, one
 * stacked-by-technology bar per run sits side by side. Stack colors encode the
 * technology; a small index under each bar (plus the run legend) identifies the run.
 */
export default function CostBreakdownChart({ runs, width = 760, height = 480 }: CostBreakdownChartProps) {
  const [hover, setHover] = useState<{ x: number; y: number; label: string } | null>(null);

  const M = { top: 20, right: 16, bottom: 74, left: 66 };
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;

  const { lcoes, yMax } = useMemo(() => {
    const set = new Set<number>();
    let mx = 0;
    runs.forEach(r => r.points.forEach(p => {
      set.add(p.lcoe);
      const tot = TECHS.reduce((s, t) => s + (Number((p as any)[t.key]) || 0), 0);
      if (tot > mx) mx = tot;
    }));
    return { lcoes: Array.from(set).sort((a, b) => a - b), yMax: mx || 1 };
  }, [runs]);

  const yTop = yMax * 1.05;
  const sy = (v: number) => M.top + ih - (v / yTop) * ih;
  const groupW = lcoes.length ? iw / lcoes.length : iw;
  const nRuns = runs.length || 1;
  const barW = Math.max(5, (groupW * 0.8) / nRuns);
  const gap = (groupW * 0.2) / (nRuns + 1);

  const yTicks = Array.from({ length: 6 }, (_, i) => (yTop * i) / 5);
  const fmt = (v: number) => (Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : v.toFixed(0));

  const hasData = runs.some(r => r.points.length > 0);

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto bg-white rounded border">
        {yTicks.map((t, i) => (
          <g key={i}>
            <line x1={M.left} y1={sy(t)} x2={M.left + iw} y2={sy(t)} stroke="#eee" />
            <text x={M.left - 8} y={sy(t) + 4} textAnchor="end" fontSize={11} fill="#374151">{fmt(t)}</text>
          </g>
        ))}

        <line x1={M.left} y1={M.top} x2={M.left} y2={M.top + ih} stroke="#9ca3af" />
        <line x1={M.left} y1={M.top + ih} x2={M.left + iw} y2={M.top + ih} stroke="#9ca3af" />
        <text x={16} y={M.top + ih / 2} textAnchor="middle" fontSize={13} fill="#111827"
              transform={`rotate(-90 16 ${M.top + ih / 2})`}>Annualized cost ($M/yr)</text>
        <text x={M.left + iw / 2} y={height - 26} textAnchor="middle" fontSize={13} fill="#111827">
          LCOE target ($/MWh)
        </text>

        {lcoes.map((lc, gi) => {
          const gx = M.left + gi * groupW;
          return (
            <g key={lc}>
              <text x={gx + groupW / 2} y={M.top + ih + 16} textAnchor="middle" fontSize={11} fill="#374151">{lc}</text>
              {runs.map((r, ri) => {
                const p = r.points.find(pt => pt.lcoe === lc);
                if (!p) return null;
                const bx = gx + gap * (ri + 1) + barW * ri;
                let acc = 0;
                return (
                  <g key={r.id}>
                    {TECHS.map(t => {
                      const val = Number((p as any)[t.key]) || 0;
                      if (val <= 0) return null;
                      const y0 = sy(acc);
                      const y1 = sy(acc + val);
                      acc += val;
                      return (
                        <rect
                          key={t.key} x={bx} y={y1} width={barW} height={Math.max(0, y0 - y1)} fill={t.color}
                          onMouseEnter={() => setHover({ x: bx + barW, y: y1,
                            label: `${r.name} · ${t.label}: $${val.toFixed(1)}M/yr (LCOE ${lc})` })}
                          onMouseLeave={() => setHover(null)}
                        />
                      );
                    })}
                    <text x={bx + barW / 2} y={M.top + ih + 30} textAnchor="middle" fontSize={9}
                          fontWeight="bold" fill={r.color}>{ri + 1}</text>
                  </g>
                );
              })}
            </g>
          );
        })}

        {hover && (
          <g>
            <rect x={Math.min(hover.x + 6, width - 262)} y={Math.max(hover.y - 22, 4)}
                  width={258} height={18} rx={4} fill="#111827" opacity={0.9} />
            <text x={Math.min(hover.x + 12, width - 256)} y={Math.max(hover.y - 9, 17)}
                  fontSize={10} fill="#fff">{hover.label}</text>
          </g>
        )}

        {!hasData && (
          <text x={width / 2} y={height / 2} textAnchor="middle" fontSize={13} fill="#6b7280">
            No cost data for the selected runs.
          </text>
        )}
      </svg>

      {/* technology legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
        {TECHS.map(t => (
          <div key={t.key} className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: t.color }} />
            <span className="text-xs text-gray-200">{t.label}</span>
          </div>
        ))}
      </div>
      {/* run key */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
        {runs.map((r, ri) => (
          <div key={r.id} className="flex items-center gap-1.5">
            <span className="text-xs font-bold w-4 text-center" style={{ color: r.color }}>{ri + 1}</span>
            <span className="text-xs text-gray-300 break-all">{r.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

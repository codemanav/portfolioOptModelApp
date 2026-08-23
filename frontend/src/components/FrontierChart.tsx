import { useMemo, useState } from 'react';

export interface FrontierPoint {
  x: number;   // average net generation (MW)
  y: number;   // LCOE target ($/MWh)
}

export interface FrontierSeries {
  id: string;
  name: string;
  color: string;
  points: FrontierPoint[];
}

interface FrontierChartProps {
  series: FrontierSeries[];
  width?: number;
  height?: number;
}

/**
 * Self-contained SVG efficient-frontier chart. Overlays one line per run.
 * X = average net generation (MW), Y = LCOE target ($/MWh) — matching the
 * model's Plot_EfficientFrontier and the PlotPortfolioOutputs multi-frontier cell.
 */
export default function FrontierChart({ series, width = 720, height = 460 }: FrontierChartProps) {
  const [hover, setHover] = useState<{ x: number; y: number; label: string } | null>(null);

  const M = { top: 24, right: 20, bottom: 56, left: 70 };
  const iw = width - M.left - M.right;
  const ih = height - M.top - M.bottom;

  const { xMin, xMax, yMin, yMax } = useMemo(() => {
    const xs: number[] = [];
    const ys: number[] = [];
    series.forEach(s => s.points.forEach(p => {
      if (Number.isFinite(p.x) && Number.isFinite(p.y)) { xs.push(p.x); ys.push(p.y); }
    }));
    if (xs.length === 0) return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    const pad = (lo: number, hi: number) => {
      const d = (hi - lo) || Math.abs(hi) || 1;
      return [lo - d * 0.08, hi + d * 0.08] as const;
    };
    const [x0, x1] = pad(Math.min(...xs), Math.max(...xs));
    const [y0, y1] = pad(Math.min(...ys), Math.max(...ys));
    return { xMin: x0, xMax: x1, yMin: y0, yMax: y1 };
  }, [series]);

  const sx = (x: number) => M.left + ((x - xMin) / (xMax - xMin || 1)) * iw;
  const sy = (y: number) => M.top + ih - ((y - yMin) / (yMax - yMin || 1)) * ih;

  const ticks = (lo: number, hi: number, n = 5) => {
    const step = (hi - lo) / n;
    return Array.from({ length: n + 1 }, (_, i) => lo + step * i);
  };
  const xTicks = ticks(xMin, xMax);
  const yTicks = ticks(yMin, yMax);
  const fmt = (v: number) => (Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : v.toFixed(1));

  const hasData = series.some(s => s.points.some(p => Number.isFinite(p.x) && Number.isFinite(p.y)));

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto bg-white rounded border">
        {/* gridlines + axis labels */}
        {yTicks.map((t, i) => (
          <g key={`y${i}`}>
            <line x1={M.left} y1={sy(t)} x2={M.left + iw} y2={sy(t)} stroke="#e5e7eb" strokeWidth={1} />
            <text x={M.left - 8} y={sy(t) + 4} textAnchor="end" fontSize={11} fill="#374151">{fmt(t)}</text>
          </g>
        ))}
        {xTicks.map((t, i) => (
          <g key={`x${i}`}>
            <line x1={sx(t)} y1={M.top} x2={sx(t)} y2={M.top + ih} stroke="#f3f4f6" strokeWidth={1} />
            <text x={sx(t)} y={M.top + ih + 18} textAnchor="middle" fontSize={11} fill="#374151">{fmt(t)}</text>
          </g>
        ))}

        {/* axes */}
        <line x1={M.left} y1={M.top} x2={M.left} y2={M.top + ih} stroke="#9ca3af" strokeWidth={1.5} />
        <line x1={M.left} y1={M.top + ih} x2={M.left + iw} y2={M.top + ih} stroke="#9ca3af" strokeWidth={1.5} />

        {/* axis titles */}
        <text x={M.left + iw / 2} y={height - 12} textAnchor="middle" fontSize={13} fill="#111827">
          Average Net Generation (MW)
        </text>
        <text x={16} y={M.top + ih / 2} textAnchor="middle" fontSize={13} fill="#111827"
              transform={`rotate(-90 16 ${M.top + ih / 2})`}>
          LCOE Target ($/MWh)
        </text>

        {/* series */}
        {series.map(s => {
          const pts = s.points
            .filter(p => Number.isFinite(p.x) && Number.isFinite(p.y))
            .sort((a, b) => a.x - b.x);
          if (pts.length === 0) return null;
          const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${sx(p.x)} ${sy(p.y)}`).join(' ');
          return (
            <g key={s.id}>
              <path d={d} fill="none" stroke={s.color} strokeWidth={2} />
              {pts.map((p, i) => (
                <circle
                  key={i} cx={sx(p.x)} cy={sy(p.y)} r={3.5} fill={s.color}
                  stroke="#fff" strokeWidth={1}
                  onMouseEnter={() => setHover({
                    x: sx(p.x), y: sy(p.y),
                    label: `${s.name}  |  ${Math.round(p.x).toLocaleString()} MW @ $${p.y.toFixed(1)}/MWh`,
                  })}
                  onMouseLeave={() => setHover(null)}
                />
              ))}
            </g>
          );
        })}

        {/* hover tooltip */}
        {hover && (
          <g>
            <rect x={Math.min(hover.x + 8, width - 250)} y={Math.max(hover.y - 26, 4)}
                  width={244} height={20} rx={4} fill="#111827" opacity={0.9} />
            <text x={Math.min(hover.x + 14, width - 244)} y={Math.max(hover.y - 12, 18)}
                  fontSize={11} fill="#fff">{hover.label}</text>
          </g>
        )}

        {!hasData && (
          <text x={width / 2} y={height / 2} textAnchor="middle" fontSize={13} fill="#6b7280">
            No frontier data for the selected runs.
          </text>
        )}
      </svg>

      {/* legend */}
      <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2">
        {series.map(s => (
          <div key={s.id} className="flex items-center gap-2">
            <span className="inline-block w-4 h-0.5" style={{ backgroundColor: s.color }} />
            <span className="text-xs text-gray-200 break-all">{s.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

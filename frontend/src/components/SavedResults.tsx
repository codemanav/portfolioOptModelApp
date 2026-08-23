import { useEffect, useState } from 'react';
import api from '@/api';
import { colorPallete } from '@/styles/constants';
import FrontierChart, { FrontierSeries } from './FrontierChart';
import CostBreakdownChart, { CostRun } from './CostBreakdownChart';

interface RunInfo {
  id: string;
  name: string;
  has_frontier: boolean;
  has_stacked_costs?: boolean;
  mtime: number;
}

interface SavedResultsProps {
  /** Load a saved run's full results into the main results panel. */
  onView: (portfolioId: string) => void;
  /** The run currently shown in the main panel (highlighted in the list). */
  activeId?: string;
}

// Distinct colors for overlaid frontiers / run identity.
const SERIES_COLORS = [
  '#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed',
  '#0891b2', '#db2777', '#65a30d', '#475569', '#ca8a04',
];

function splitName(name: string): [string, string] {
  const i = name.indexOf('/');
  return i === -1 ? [name, ''] : [name.slice(0, i), name.slice(i + 1)];
}

export default function SavedResults({ onView, activeId }: SavedResultsProps) {
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [series, setSeries] = useState<FrontierSeries[]>([]);
  const [costRuns, setCostRuns] = useState<CostRun[]>([]);
  const [comparing, setComparing] = useState(false);

  const loadRuns = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.listPortfolioRuns();
      setRuns(res.data.runs || []);
    } catch (e: any) {
      setError('Could not load saved runs: ' + (e?.message || 'unknown error'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadRuns(); }, []);

  const toggleSelect = (id: string) => {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const clearComparison = () => {
    setSelected([]);
    setSeries([]);
    setCostRuns([]);
  };

  const compareFrontiers = async () => {
    setComparing(true);
    setError('');
    try {
      const results = await Promise.all(
        selected.map(async (id, idx) => {
          const color = SERIES_COLORS[idx % SERIES_COLORS.length];
          try {
            const res = await api.getFrontierData(id);
            const raw: any[] = res.data.points || [];
            const frontierPts = raw
              .filter((p) => p.total_mw != null && p.lcoe_target != null)
              .map((p) => ({ x: p.total_mw, y: p.lcoe_target }));
            const costPts = raw
              .filter((p) => p.lcoe_target != null)
              .map((p) => ({
                lcoe: p.lcoe_target,
                wind: p.cost_wind || 0,
                wave: p.cost_wave || 0,
                kite: p.cost_kite || 0,
                coaxial: p.cost_coaxial || 0,
                transmission: p.cost_transmission || 0,
              }));
            return {
              frontier: { id, name: id, color, points: frontierPts } as FrontierSeries,
              cost: { id, name: id, color, points: costPts } as CostRun,
            };
          } catch {
            return {
              frontier: { id, name: id + ' (no data)', color, points: [] } as FrontierSeries,
              cost: { id, name: id, color, points: [] } as CostRun,
            };
          }
        })
      );
      setSeries(results.map((r) => r.frontier));
      setCostRuns(results.map((r) => r.cost));
    } catch (e: any) {
      setError('Could not build comparison: ' + (e?.message || 'unknown error'));
    } finally {
      setComparing(false);
    }
  };

  return (
    <div className="w-full mt-10 mb-12">
      <div className="flex items-center justify-between mb-4">
        <p className="not-italic underline decoration-4 underline-offset-4 text-lg"
           style={{ textDecorationColor: colorPallete.primary }}>
          Saved Results
        </p>
        <button
          onClick={loadRuns}
          className="px-3 py-1.5 text-sm font-medium text-white rounded-lg hover:opacity-80"
          style={{ backgroundColor: colorPallete.primary }}
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="w-full bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded mb-3 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-300">Loading saved runs…</p>
      ) : runs.length === 0 ? (
        <p className="text-sm text-gray-400 italic">No saved runs yet. Run a simulation to see it here.</p>
      ) : (
        <>
          <p className="text-xs text-gray-400 mb-2">
            Check runs to overlay their efficient frontiers and compare annualized cost breakdowns, or click View to open a saved run in the panel above.
          </p>
          <div className="border border-gray-700 rounded-lg divide-y divide-gray-700 max-h-80 overflow-y-auto">
            {runs.map(run => {
              const [primary, secondary] = splitName(run.name);
              const isActive = run.id === activeId;
              return (
                <div key={run.id}
                     className={`flex items-center gap-3 px-3 py-2 ${isActive ? 'bg-blue-900/30' : ''}`}>
                  <input
                    type="checkbox"
                    className="shrink-0 border-gray-300 rounded text-blue-600 focus:ring-blue-500"
                    checked={selected.includes(run.id)}
                    onChange={() => toggleSelect(run.id)}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-100 break-all">{primary}</p>
                    {secondary && <p className="text-xs text-gray-400 break-all">{secondary}</p>}
                  </div>
                  {!run.has_frontier && (
                    <span className="text-[10px] text-amber-400 whitespace-nowrap">no frontier</span>
                  )}
                  <button
                    onClick={() => onView(run.id)}
                    className="shrink-0 px-3 py-1 text-xs font-medium text-white rounded hover:opacity-80"
                    style={{ backgroundColor: colorPallete.primary }}
                  >
                    View
                  </button>
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-3 mt-3">
            <button
              onClick={compareFrontiers}
              disabled={selected.length === 0 || comparing}
              className="px-4 py-2 text-sm font-medium text-white rounded-lg hover:opacity-80 disabled:opacity-40"
              style={{ backgroundColor: '#059669' }}
            >
              {comparing ? 'Building…' : `Compare${selected.length ? ` (${selected.length})` : ''}`}
            </button>
            {selected.length > 0 && (
              <button
                onClick={clearComparison}
                className="px-3 py-2 text-sm font-medium text-gray-200 rounded-lg border border-gray-600 hover:bg-gray-800"
              >
                Clear
              </button>
            )}
          </div>

          {series.length > 0 && (
            <div className="mt-5">
              <p className="mb-2 text-sm text-gray-200">Efficient Frontier Comparison</p>
              <FrontierChart series={series} />
            </div>
          )}

          {costRuns.some((r) => r.points.length > 0) && (
            <div className="mt-6">
              <p className="mb-2 text-sm text-gray-200">Annualized Cost Breakdown by Technology</p>
              <CostBreakdownChart runs={costRuns} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

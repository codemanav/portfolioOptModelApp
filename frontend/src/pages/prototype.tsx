import ResourceSelect from '../components/ResourceSelect';
import TransmissionCapSelect from '@/components/TransmissionCapSelect';
import Input from '@/components/Input';
import PercentLoader from '@/components/PercentLoader';
import { colorPallete } from '@/styles/constants';
import api from '../api';
import { useEffect, useState } from 'react';

interface DesignOption {
  name: string;
  label: string;
  path: string;
  design_id?: number;
  capacity_mw?: number;
}

interface AvailableData {
  wind: DesignOption[];
  wave: DesignOption[];
  kite: DesignOption[];
  transmission: DesignOption[];
}

const emptyAvailable: AvailableData = { wind: [], wave: [], kite: [], transmission: [] };

const Prototype = () => {
    // ---- Available data (populated by /availableData based on state) ----
    const [available, setAvailable] = useState<AvailableData>(emptyAvailable);

    // ---- User selections ----
    const [selectedState, setSelectedState] = useState('va');
    const [selectedWind, setSelectedWind] = useState<string[]>([]);
    const [selectedWave, setSelectedWave] = useState<string[]>([]);
    const [selectedKite, setSelectedKite] = useState<string[]>([]);
    const [selectedTransmission, setSelectedTransmission] = useState('');

    // ---- Optimization parameters ----
    // max_*  = MaxDesigns (max number of distinct designs the optimizer may activate)
    // min_*  = MinNumTurb (minimum total turbines/devices that must be deployed)
    const [params, setParams] = useState({
        lcoe_max: 200,
        lcoe_min: 40,
        lcoe_step: 2,
        max_system_radius: 30,
        WindTurbinesPerSite: 4,
        KiteTurbinesPerSite: 390,
        WaveTurbinesPerSite: 300,
        max_wind: 1,
        min_wind: 1,
        max_kite: 1,
        min_kite: 1,
        max_wave: 1,
        min_wave: 1,
    });

    // ---- UI state ----
    const [files, setFiles] = useState<File[]>([]);
    const [portfolio, setPortfolio] = useState<string[]>([]);
    const [loading, setLoading] = useState({ active: false, value: 0, message: '' });
    const [imgSrc, setImgSrc] = useState('');
    const [error, setError] = useState('');

    // ---- Results browser state ----
    const [portfolioId, setPortfolioId] = useState('');
    const [availableLcoe, setAvailableLcoe] = useState<string[]>([]);
    const [runLevelFiles, setRunLevelFiles] = useState<string[]>([]);
    const [selectedLcoe, setSelectedLcoe] = useState('');
    const [selectedPlotType, setSelectedPlotType] = useState('');
    const [resultPlotSrc, setResultPlotSrc] = useState('');
    const [summaryData, setSummaryData] = useState<string[][] | null>(null);
    const [showSummary, setShowSummary] = useState(false);

    // ---- Fetch available data when state changes ----
    useEffect(() => {
        const fetchData = async () => {
            try {
                setError('');
                const response = await api.availableData(selectedState);
                setAvailable(response.data);
                // Clear selections when state changes
                setSelectedWind([]);
                setSelectedWave([]);
                setSelectedKite([]);
                setSelectedTransmission('');
            } catch (e: any) {
                console.error('Failed to fetch available data:', e);
                setAvailable(emptyAvailable);
                setError('Failed to connect to backend. Is the server running?');
            }
        };
        fetchData();
    }, [selectedState]);

    // ---- Auto-select transmission when available data loads ----
    useEffect(() => {
        if (available.transmission.length > 0 && !selectedTransmission) {
            setSelectedTransmission(available.transmission[0].path);
        }
    }, [available]);

    // ---- Toggle resource selection ----
    const handleToggle = (tech: 'wind' | 'wave' | 'kite', path: string) => {
        const setters = { wind: setSelectedWind, wave: setSelectedWave, kite: setSelectedKite };
        const current = { wind: selectedWind, wave: selectedWave, kite: selectedKite }[tech];
        const setter = setters[tech];
        if (current.includes(path)) {
            setter(current.filter(p => p !== path));
        } else {
            setter([...current, path]);
        }
    };

    // ---- File upload for custom resources ----
    const handleFileChange = (e: any) => {
        const selectedFiles = Array.from(e.target.files) as File[];
        setFiles(selectedFiles);
    };

    const handleUpload = async () => {
        if (!files || files.length === 0) return;
        const formData = new FormData();
        files.forEach(file => formData.append("files", file));
        try {
            const response = await api.resourceUpload(formData);
            console.log(response);
            // Re-fetch available data after upload
            const refreshed = await api.availableData(selectedState);
            setAvailable(refreshed.data);
        } catch (e: any) {
            setError('Upload failed: ' + (e.message || 'unknown error'));
        }
    };

    // ---- Run optimization ----
    const handleRunOptimization = async () => {
        setError('');
        setImgSrc('');
        setPortfolio([]);

        // Validate selections
        const hasAnyResource = selectedWind.length > 0 || selectedWave.length > 0 || selectedKite.length > 0;
        if (!hasAnyResource) {
            setError('Please select at least one resource (wind, wave, or kite).');
            return;
        }
        if (!selectedTransmission) {
            setError('Please select a transmission capacity.');
            return;
        }

        setLoading({ active: true, value: 10, message: 'Starting optimization...' });

        try {
            // Zero out constraints for techs that aren't selected; otherwise use user values as-is
            const autoParams = {
                ...params,
                max_wind: selectedWind.length > 0 ? params.max_wind : 0,
                min_wind: selectedWind.length > 0 ? params.min_wind : 0,
                max_kite: selectedKite.length > 0 ? params.max_kite : 0,
                min_kite: selectedKite.length > 0 ? params.min_kite : 0,
                max_wave: selectedWave.length > 0 ? params.max_wave : 0,
                min_wave: selectedWave.length > 0 ? params.min_wave : 0,
            };

            setLoading({ active: true, value: 30, message: 'Running portfolio optimization...' });

            const optimizationPayload = {
                wind: selectedWind,
                wave: selectedWave,
                kite: selectedKite,
                transmission: [selectedTransmission],
                ...autoParams,
            };

            console.log('Optimization payload:', optimizationPayload);
            const data = await api.portfolioOptimization(optimizationPayload);
            console.log('Optimization result:', data);

            const savePaths = data.data.save_path;
            setPortfolio(savePaths);

            setLoading({ active: true, value: 80, message: 'Generating plots...' });

            // Generate efficient frontier plot
            try {
                const response = await api.portfolioPlots({ portfolio: savePaths });
                const imageBlob = new Blob([response.data], { type: 'image/png' });
                const imageURL = URL.createObjectURL(imageBlob);
                setImgSrc(imageURL);
            } catch (plotErr: any) {
                console.warn('Efficient frontier plot generation failed (may be ok if some LCOEs were infeasible):', plotErr);
            }

            // Extract portfolio ID from save path and load detailed results
            // save_path looks like "/app/Portfolios/TechCase_TransCase.npz"
            if (savePaths.length > 0) {
                const fullPath = savePaths[0];
                const fileName = fullPath.split('/').pop() || '';
                const pid = fileName.replace('.npz', '');
                await loadResults(pid);
            }

            setLoading({ active: false, value: 100, message: 'Complete!' });
        } catch (e: any) {
            console.error('Optimization error:', e);
            const msg = e.response?.data?.error || e.message || 'Unknown error';
            setError('Optimization failed: ' + msg);
            setLoading({ active: false, value: 0, message: '' });
        }
    };

    const handleParamChange = (key: string, value: number) => {
        setParams(prev => ({ ...prev, [key]: value }));
    };

    // ---- Load available results for a portfolio run ----
    const loadResults = async (pid: string) => {
        try {
            setPortfolioId(pid);
            setSelectedLcoe('');
            setSelectedPlotType('');
            setResultPlotSrc('');
            setSummaryData(null);
            setShowSummary(false);

            const res = await api.listPortfolioPlots(pid);
            const data = res.data;
            setRunLevelFiles(data.run_level || []);
            const lcoeKeys = Object.keys(data.per_lcoe || {}).sort((a, b) => {
                const numA = parseInt(a.replace('LCOE_', ''));
                const numB = parseInt(b.replace('LCOE_', ''));
                return numB - numA; // descending
            });
            setAvailableLcoe(lcoeKeys);
        } catch (e: any) {
            console.error('Failed to load results:', e);
        }
    };

    // ---- Fetch a specific LCOE plot ----
    const handleViewPlot = async (lcoe: string, plotType: string) => {
        if (!lcoe || !plotType) return;
        setSelectedLcoe(lcoe);
        setSelectedPlotType(plotType);
        setShowSummary(false);
        try {
            const lcoeNum = parseInt(lcoe.replace('LCOE_', ''));
            const res = await api.getLcoePlot(portfolioId, lcoeNum, plotType);
            const blob = new Blob([res.data], { type: 'image/png' });
            setResultPlotSrc(URL.createObjectURL(blob));
        } catch (e: any) {
            console.error('Failed to load plot:', e);
            setResultPlotSrc('');
        }
    };

    // ---- Fetch a run-level plot (efficient frontier or stacked costs) ----
    const handleViewRunPlot = async (plotName: string) => {
        setShowSummary(false);
        setSelectedLcoe('');
        setSelectedPlotType('');
        try {
            let res;
            if (plotName.includes('EfficientFrontier')) {
                res = await api.getEfficientFrontier(portfolioId);
            } else if (plotName.includes('StackedCosts')) {
                res = await api.getStackedCosts(portfolioId);
            } else {
                return;
            }
            const blob = new Blob([res.data], { type: 'image/png' });
            setResultPlotSrc(URL.createObjectURL(blob));
        } catch (e: any) {
            console.error('Failed to load run plot:', e);
            setResultPlotSrc('');
        }
    };

    // ---- Fetch and display summary CSV ----
    const handleViewSummary = async () => {
        setResultPlotSrc('');
        setSelectedLcoe('');
        setSelectedPlotType('');
        try {
            const res = await api.getPortfolioSummary(portfolioId);
            const text = typeof res.data === 'string' ? res.data : await res.data.text?.() || String(res.data);
            const rows = text.trim().split('\n').map((row: string) => row.split(','));
            setSummaryData(rows);
            setShowSummary(true);
        } catch (e: any) {
            console.error('Failed to load summary:', e);
            setSummaryData(null);
        }
    };

    return (
        <div className='w-2/3 lg:w-1/2 flex flex-col items-center justify-center'>
            {loading.active && (
                <div className='w-full'>
                    <span className="block text-sm text-gray-600 mb-1">{loading.message} ({loading.value}%)</span>
                    <PercentLoader width={loading.value}/>
                </div>
            )}

            {error && (
                <div className="w-full bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
                    {error}
                </div>
            )}

            <div className='w-full flex flex-col justify-items-start items-start'>
                <span className="self-center text-4xl mt-5 mb-5 whitespace-nowrap align-middle h-full">
                    Portfolio Optimization
                </span>

                {/* ---- STATE SELECTION ---- */}
                <div className='m-3 mb-6 w-full'>
                    <p className="mb-3 not-italic underline decoration-4 underline-offset-4"
                       style={{ textDecorationColor: colorPallete.primary }}>
                        Location
                    </p>
                    <label htmlFor="state-select" className="block mb-2 text-sm font-medium text-gray-900">
                        Select State
                    </label>
                    <select
                        id="state-select"
                        className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5"
                        value={selectedState}
                        onChange={(e) => setSelectedState(e.target.value)}
                    >
                        <option value="fl">Florida</option>
                        <option value="ga">Georgia</option>
                        <option value="sc">South Carolina</option>
                        <option value="nc">North Carolina</option>
                        <option value="va">Virginia</option>
                        <option value="md">Maryland</option>
                        <option value="de">Delaware</option>
                        <option value="nj">New Jersey</option>
                        <option value="ny">New York</option>
                        <option value="ct">Connecticut</option>
                        <option value="ri">Rhode Island</option>
                        <option value="ma">Massachusetts</option>
                        <option value="nh">New Hampshire</option>
                        <option value="me">Maine</option>
                    </select>
                </div>

                {/* ---- RESOURCE SELECTION ---- */}
                <div className='m-3 mb-6 w-full'>
                    <p className="mb-3 not-italic underline decoration-4 underline-offset-4"
                       style={{ textDecorationColor: colorPallete.primary }}>
                        Resources
                    </p>
                    <ResourceSelect
                        available={available}
                        selectedWind={selectedWind}
                        selectedWave={selectedWave}
                        selectedKite={selectedKite}
                        onToggle={handleToggle}
                    />

                    {/* Summary of selections */}
                    <div className="mt-3 text-sm text-gray-600">
                        {selectedWind.length > 0 && <p>Wind: {selectedWind.length} design(s)</p>}
                        {selectedWave.length > 0 && <p>Wave: {selectedWave.length} design(s)</p>}
                        {selectedKite.length > 0 && <p>Kite: {selectedKite.length} design(s)</p>}
                    </div>

                    {/* File upload */}
                    <div className="mt-4">
                        <label className="block mb-2 text-sm font-medium text-gray-900" htmlFor="file-upload">
                            Upload custom resource files (.npz)
                        </label>
                        <input
                            className="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50"
                            id="file-upload"
                            type="file"
                            multiple
                            accept=".npz"
                            onChange={handleFileChange}
                        />
                        {files.length > 0 && (
                            <button
                                className="inline-flex items-center w-full justify-center mt-3 px-3 py-2 text-sm font-medium text-center text-white rounded-lg hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300"
                                style={{ backgroundColor: colorPallete.primary }}
                                onClick={handleUpload}
                            >
                                Upload {files.length} file(s)
                            </button>
                        )}
                    </div>
                </div>

                {/* ---- TECHNICALS ---- */}
                <div className='m-3 mb-6 w-full'>
                    <p className="mb-3 not-italic underline decoration-4 underline-offset-4"
                       style={{ textDecorationColor: colorPallete.primary }}>
                        Technical Parameters
                    </p>
                    <div className='grid grid-cols-2 gap-6 justify-center'>
                        <TransmissionCapSelect
                            available={available.transmission}
                            selected={selectedTransmission}
                            onSelect={setSelectedTransmission}
                        />
                        <Input label='Max System Radius'
                               type='number' step="1" placeholder='30' curr='km'
                               value={params.max_system_radius}
                               onChange={(e: any) => handleParamChange('max_system_radius', Number(e.target.value))}
                        />

                        {selectedWind.length > 0 && (
                            <>
                                <Input label='Wind Devices / Site'
                                       type='number' step="1" placeholder='4' curr=''
                                       value={params.WindTurbinesPerSite}
                                       onChange={(e: any) => handleParamChange('WindTurbinesPerSite', Number(e.target.value))}
                                />
                                <Input label='Max Wind Designs'
                                       type='number' step="1" placeholder='1' curr=''
                                       value={params.max_wind}
                                       onChange={(e: any) => handleParamChange('max_wind', Number(e.target.value))}
                                />
                                <Input label='Min Wind Turbines'
                                       type='number' step="1" placeholder='1' curr=''
                                       value={params.min_wind}
                                       onChange={(e: any) => handleParamChange('min_wind', Number(e.target.value))}
                                />
                            </>
                        )}
                        {selectedKite.length > 0 && (
                            <>
                                <Input label='Kite Devices / Site'
                                       type='number' step="1" placeholder='390' curr=''
                                       value={params.KiteTurbinesPerSite}
                                       onChange={(e: any) => handleParamChange('KiteTurbinesPerSite', Number(e.target.value))}
                                />
                                <Input label='Max Kite Designs'
                                       type='number' step="1" placeholder='1' curr=''
                                       value={params.max_kite}
                                       onChange={(e: any) => handleParamChange('max_kite', Number(e.target.value))}
                                />
                                <Input label='Min Kite Turbines'
                                       type='number' step="1" placeholder='1' curr=''
                                       value={params.min_kite}
                                       onChange={(e: any) => handleParamChange('min_kite', Number(e.target.value))}
                                />
                            </>
                        )}
                        {selectedWave.length > 0 && (
                            <>
                                <Input label='Wave Devices / Site'
                                       type='number' step="1" placeholder='300' curr=''
                                       value={params.WaveTurbinesPerSite}
                                       onChange={(e: any) => handleParamChange('WaveTurbinesPerSite', Number(e.target.value))}
                                />
                                <Input label='Max Wave Designs'
                                       type='number' step="1" placeholder='1' curr=''
                                       value={params.max_wave}
                                       onChange={(e: any) => handleParamChange('max_wave', Number(e.target.value))}
                                />
                                <Input label='Min Wave Devices'
                                       type='number' step="1" placeholder='1' curr=''
                                       value={params.min_wave}
                                       onChange={(e: any) => handleParamChange('min_wave', Number(e.target.value))}
                                />
                            </>
                        )}

                        <Input label='LCOE Max'
                               type='number' step="1" placeholder='200' curr='$/MWh'
                               value={params.lcoe_max}
                               onChange={(e: any) => handleParamChange('lcoe_max', Number(e.target.value))}
                        />
                        <Input label='LCOE Min'
                               type='number' step="1" placeholder='40' curr='$/MWh'
                               value={params.lcoe_min}
                               onChange={(e: any) => handleParamChange('lcoe_min', Number(e.target.value))}
                        />
                        <Input label='LCOE Step Size'
                               type='number' step="1" placeholder='2' curr=''
                               value={params.lcoe_step}
                               onChange={(e: any) => handleParamChange('lcoe_step', Number(e.target.value))}
                        />
                    </div>
                </div>

                {/* ---- RUN BUTTON ---- */}
                <button
                    onClick={handleRunOptimization}
                    disabled={loading.active}
                    className="inline-flex items-center w-full justify-center m-3 mt-4 px-3 py-3 text-sm font-medium text-center text-white rounded-lg hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 disabled:opacity-50"
                    style={{ backgroundColor: colorPallete.primary }}
                >
                    {loading.active ? 'Running...' : 'Generate Efficient Frontiers'}
                </button>
            </div>

            {/* ---- RESULTS ---- */}
            {(imgSrc || portfolioId) && (
                <div className="w-full mt-8 mb-12">
                    <p className="mb-4 not-italic underline decoration-4 underline-offset-4 text-lg"
                       style={{ textDecorationColor: colorPallete.primary }}>
                        Results
                    </p>

                    {/* Run-level plots row */}
                    <div className="flex flex-wrap gap-2 mb-4">
                        {runLevelFiles.filter(f => f.endsWith('.png')).map(f => (
                            <button
                                key={f}
                                onClick={() => handleViewRunPlot(f)}
                                className="px-3 py-2 text-sm font-medium text-white rounded-lg hover:opacity-80"
                                style={{ backgroundColor: colorPallete.primary }}
                            >
                                {f.replace('Plot_', '').replace('.png', '').replace(/([A-Z])/g, ' $1').trim()}
                            </button>
                        ))}
                        {runLevelFiles.some(f => f.endsWith('.csv')) && (
                            <button
                                onClick={handleViewSummary}
                                className="px-3 py-2 text-sm font-medium text-white rounded-lg hover:opacity-80"
                                style={{ backgroundColor: '#059669' }}
                            >
                                View Summary
                            </button>
                        )}
                    </div>

                    {/* LCOE selector + plot type selector */}
                    {availableLcoe.length > 0 && (
                        <div className="flex gap-4 mb-4">
                            <div className="flex-1">
                                <label className="block mb-1 text-sm font-medium text-gray-900">LCOE Target</label>
                                <select
                                    className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5"
                                    value={selectedLcoe}
                                    onChange={(e) => {
                                        const lcoe = e.target.value;
                                        setSelectedLcoe(lcoe);
                                        if (lcoe && selectedPlotType) handleViewPlot(lcoe, selectedPlotType);
                                    }}
                                >
                                    <option value="">Select LCOE...</option>
                                    {availableLcoe.map(lcoe => (
                                        <option key={lcoe} value={lcoe}>
                                            {lcoe.replace('_', ' = $')} /MWh
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex-1">
                                <label className="block mb-1 text-sm font-medium text-gray-900">Plot Type</label>
                                <select
                                    className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5"
                                    value={selectedPlotType}
                                    onChange={(e) => {
                                        const pt = e.target.value;
                                        setSelectedPlotType(pt);
                                        if (selectedLcoe && pt) handleViewPlot(selectedLcoe, pt);
                                    }}
                                >
                                    <option value="">Select plot...</option>
                                    <option value="totalGeneration">Total Generation</option>
                                    <option value="stackedGeneration">Stacked Generation by Tech</option>
                                    <option value="curtailment">Curtailment</option>
                                    <option value="deploymentMap">Deployment Map</option>
                                </select>
                            </div>
                        </div>
                    )}

                    {/* Display area: plot image or summary table */}
                    {resultPlotSrc && (
                        <div className="mt-4">
                            <img src={resultPlotSrc} className="w-full h-auto border rounded" alt="Result Plot" />
                        </div>
                    )}

                    {showSummary && summaryData && (
                        <div className="mt-4 overflow-x-auto">
                            <table className="min-w-full text-sm border border-gray-300">
                                <thead>
                                    {summaryData.length > 0 && (
                                        <tr className="bg-gray-100">
                                            {summaryData[0].map((cell, i) => (
                                                <th key={i} className="px-3 py-2 border border-gray-300 text-left font-medium">
                                                    {cell}
                                                </th>
                                            ))}
                                        </tr>
                                    )}
                                </thead>
                                <tbody>
                                    {summaryData.slice(1).map((row, ri) => (
                                        <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                            {row.map((cell, ci) => (
                                                <td key={ci} className="px-3 py-2 border border-gray-300">
                                                    {cell}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {/* Fallback: show efficient frontier from initial plot call */}
                    {imgSrc && !resultPlotSrc && !showSummary && (
                        <div className="mt-4">
                            <p className="mb-2 text-sm text-gray-600">Efficient Frontier (combined)</p>
                            <img id='result-image' src={imgSrc} className='w-full h-auto border rounded' alt="Efficient Frontier" />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default Prototype;

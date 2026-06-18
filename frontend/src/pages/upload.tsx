import Input from '@/components/Input';
import PercentLoader from '@/components/PercentLoader';
import { colorPallete } from '@/styles/constants';
import api from '../api';
import { useMemo, useState } from 'react';

const SURFACE_TECHNOLOGIES = [
    { value: 'kite', label: 'Kite' },
    { value: 'ocean_current', label: 'Ocean Current' },
    { value: 'wave', label: 'Wave' },
    { value: 'polamis', label: 'Pelamis' },
    { value: 'rm3', label: 'RM3' },
];

const CURVE_TECHNOLOGIES = [
    { value: 'wind', label: 'Wind' },
    { value: 'coaxial', label: 'Coaxial' },
];

interface UploadResult {
    message: string;
    input_file: string;
    technology: string;
    model_kind: string;
    output_files: { npz: string; csv: string };
    downloads: { npz: string; csv: string };
    shape: { x: number[]; y: number[] | null; power: number[] };
}

const Upload = () => {
    const [technology, setTechnology] = useState('kite');
    const [file, setFile] = useState<File | null>(null);
    const [xColumn, setXColumn] = useState('Depth');
    const [yColumn, setYColumn] = useState('Velocity');
    const [powerColumn, setPowerColumn] = useState('Power');
    const [gridPoints, setGridPoints] = useState(50);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [result, setResult] = useState<UploadResult | null>(null);

    const isCurveTechnology = useMemo(
        () => CURVE_TECHNOLOGIES.some((tech) => tech.value === technology),
        [technology]
    );

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selected = e.target.files?.[0] ?? null;
        setFile(selected);
        setResult(null);
        setError('');
    };

    const handleSubmit = async () => {
        if (!file) {
            setError('Please select a CSV file to upload.');
            return;
        }

        setLoading(true);
        setError('');
        setResult(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await api.uploadPowerSurface(formData, {
                technology,
                x_column: xColumn,
                y_column: yColumn,
                power_column: powerColumn,
                grid_points: String(gridPoints),
            });
            setResult(response.data);
        } catch (e: any) {
            const msg = e.response?.data?.error || e.message || 'Upload failed';
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    const getDownloadFilename = (path: string) => path.split('/').pop() || path;

    return (
        <div className="w-2/3 lg:w-1/2 flex flex-col items-center justify-center">
            <div className="w-full flex flex-col justify-items-start items-start">
                <span className="self-center text-4xl mt-5 mb-5 whitespace-nowrap align-middle h-full">
                    Upload
                </span>

                <p className="mb-6 text-sm text-gray-600">
                    Upload a CSV with power data to generate interpolated surface or curve models.
                    Download the resulting <code className="text-xs bg-gray-100 px-1 rounded">.npz</code> and{' '}
                    <code className="text-xs bg-gray-100 px-1 rounded">.csv</code> files after processing.
                </p>

                {error && (
                    <div className="w-full bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
                        {error}
                    </div>
                )}

                <div className="m-3 mb-6 w-full">
                    <p
                        className="mb-3 not-italic underline decoration-4 underline-offset-4"
                        style={{ textDecorationColor: colorPallete.primary }}
                    >
                        Upload Settings
                    </p>

                    <label htmlFor="technology-select" className="block mb-2 text-sm font-medium text-gray-900">
                        Technology
                    </label>
                    <select
                        id="technology-select"
                        className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 mb-4"
                        value={technology}
                        onChange={(e) => setTechnology(e.target.value)}
                    >
                        <optgroup label="2D Surface Models">
                            {SURFACE_TECHNOLOGIES.map((tech) => (
                                <option key={tech.value} value={tech.value}>
                                    {tech.label}
                                </option>
                            ))}
                        </optgroup>
                        <optgroup label="1D Curve Models">
                            {CURVE_TECHNOLOGIES.map((tech) => (
                                <option key={tech.value} value={tech.value}>
                                    {tech.label}
                                </option>
                            ))}
                        </optgroup>
                    </select>

                    <label className="block mb-2 text-sm font-medium text-gray-900" htmlFor="upload-file">
                        CSV File
                    </label>
                    <input
                        className="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 mb-4"
                        id="upload-file"
                        type="file"
                        accept=".csv"
                        onChange={handleFileChange}
                    />

                    <button
                        type="button"
                        onClick={() => setShowAdvanced((prev) => !prev)}
                        className="text-sm text-gray-700 underline mb-3"
                    >
                        {showAdvanced ? 'Hide' : 'Show'} column & grid options
                    </button>

                    {showAdvanced && (
                        <div className="grid grid-cols-2 gap-4 mb-4">
                            {!isCurveTechnology && (
                                <div>
                                    <label className="block mb-2 text-sm font-medium text-gray-900">X Column</label>
                                    <input
                                        className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5"
                                        value={xColumn}
                                        onChange={(e) => setXColumn(e.target.value)}
                                    />
                                </div>
                            )}
                            <div>
                                <label className="block mb-2 text-sm font-medium text-gray-900">
                                    {isCurveTechnology ? 'X-Axis Column' : 'Y Column'}
                                </label>
                                <input
                                    className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5"
                                    value={yColumn}
                                    onChange={(e) => setYColumn(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block mb-2 text-sm font-medium text-gray-900">Power Column</label>
                                <input
                                    className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5"
                                    value={powerColumn}
                                    onChange={(e) => setPowerColumn(e.target.value)}
                                />
                            </div>
                            <Input
                                label="Grid Points"
                                type="number"
                                step="1"
                                placeholder="50"
                                curr=""
                                value={gridPoints}
                                onChange={(e) => setGridPoints(Number(e.target.value))}
                            />
                        </div>
                    )}

                    <p className="text-xs text-gray-500 mb-4">
                        {isCurveTechnology
                            ? 'Curve models use the x-axis and power columns. Default: Velocity, Power.'
                            : 'Surface models use depth, velocity, and power columns. Default: Depth, Velocity, Power.'}
                    </p>

                    <button
                        onClick={handleSubmit}
                        disabled={loading || !file}
                        className="inline-flex items-center w-full justify-center px-3 py-3 text-sm font-medium text-center text-white rounded-lg hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 disabled:opacity-50"
                        style={{ backgroundColor: colorPallete.primary }}
                    >
                        {loading ? 'Generating...' : 'Generate Power Surface'}
                    </button>

                    {loading && (
                        <div className="w-full mt-4">
                            <span className="block text-sm text-gray-600 mb-1">Processing CSV...</span>
                            <PercentLoader width={60} />
                        </div>
                    )}
                </div>

                {result && (
                    <div className="m-3 mb-12 w-full">
                        <p
                            className="mb-3 not-italic underline decoration-4 underline-offset-4"
                            style={{ textDecorationColor: colorPallete.primary }}
                        >
                            Generated Files
                        </p>

                        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4 text-sm">
                            {result.message}
                        </div>

                        <div className="grid grid-cols-2 gap-3 text-sm text-gray-700 mb-4">
                            <p><span className="font-medium">Input:</span> {result.input_file}</p>
                            <p><span className="font-medium">Technology:</span> {result.technology}</p>
                            <p><span className="font-medium">Model type:</span> {result.model_kind}</p>
                            <p>
                                <span className="font-medium">Grid shape:</span>{' '}
                                {result.shape.y
                                    ? `${result.shape.x[0]} x ${result.shape.y[0]}`
                                    : `${result.shape.x[0]} points`}
                            </p>
                        </div>

                        <div className="flex flex-col sm:flex-row gap-3">
                            <a
                                href={api.downloadGeneratedSurfaceUrl(getDownloadFilename(result.output_files.npz))}
                                download
                                className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90"
                                style={{ backgroundColor: colorPallete.primary }}
                            >
                                Download .npz
                            </a>
                            <a
                                href={api.downloadGeneratedSurfaceUrl(getDownloadFilename(result.output_files.csv))}
                                download
                                className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90"
                                style={{ backgroundColor: '#2563eb' }}
                            >
                                Download .csv
                            </a>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Upload;

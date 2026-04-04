import MoneyInput from '@/components/MoneyInput';
import Select from '../components/ResourceSelect';

import about from '../static/about';
import { colorPallete } from '@/styles/constants';
import Input from '@/components/Input';
import TransmissionCapSelect from '@/components/TransmissionCapSelect';
import YearSelect from '@/components/YearSelect';
import api from '../api';
import { useEffect, useState } from 'react';
import PercentLoader from '@/components/PercentLoader';

const Prototype = () => {
    const [ useApiData, setUseApiData ] = useState({
        wind: [],
        wave: [],
        kite: [],
        coaxial: [],
        transmission: ['Transmission/Transmission_300MW.npz'],
        max_system_radius: 30,
        lcoe_max: 120,
        lcoe_min: 100,
        lcoe_step: 2,
        start_year: 2007,
        end_year: 2007,
        max_wind: 1,
        min_wind: 1,
        max_kite: 1,
        min_kite: 1,
        max_wave: 0,
        min_wave: 0,
        max_coaxial: 0,
        min_coaxial: 0,
        WindTurbinesPerSite: 4,
        WindResolutionKm: 2,
        KiteTurbinesPerSite: 390, 
        WaveTurbinesPerSite: 300, 
        CoaxialTurbinesPerSite: 390,
        lat_start: 0,
        lat_end: 0,
        lon_start: 0,
        lon_end: 0,
    });

    // map each option to its coordinates
    const STATE_RANGES: Record<string, { lat: [number, number]; lon: [number, number] }> = {
        fl: { lat: [24.2, 31.0], lon: [-81, -65] },
        ga: { lat: [30.6, 32.2], lon: [-81, -65] },
        sc: { lat: [32.0, 34.0], lon: [-81, -65] },
        nc: { lat: [33.7, 36.6], lon: [-81, -65] },
        va: { lat: [36.4, 38.2], lon: [-81, -65] },
        md: { lat: [38.0, 38.6], lon: [-81, -65] },
        de: { lat: [38.4, 39.5], lon: [-81, -65] },
        nj: { lat: [38.8, 41.0], lon: [-81, -65] },
        ny: { lat: [40.4, 41.5], lon: [-81, -65] },
        ct: { lat: [41.2, 41.5], lon: [-81, -65] },
        ri: { lat: [41.1, 41.5], lon: [-81, -65] },
        ma: { lat: [41.1, 42.9], lon: [-81, -65] },
        nh: { lat: [42.8, 43.3], lon: [-81, -65] },
        me: { lat: [43.0, 45.5], lon: [-81, -65] },
        custom: { lat: [0, 0], lon: [0, 0] }
    };

    const [files, setFiles] = useState([]);

    const [ portfolio, setPortfolio ] = useState([]);

    const [ state, setState ] = useState({
        load: false,
        value: 0
    });

    const [imgSrc, setImgSrc] = useState("");

    const [coords, setCoords] = useState({
            latStart: 0,
            latEnd: 0,
            lonStart: 0,
            lonEnd: 0,})

    useEffect(() => {
        console.log(useApiData)
    }, [useApiData]);

    useEffect(() => {
        console.log(state);
    }, [state]);

    useEffect(() => {
        setUseApiData(prev => ({
            ...prev,
            lat_start: coords.latStart,
            lat_end: coords.latEnd,
            lon_start: coords.lonStart,
            lon_end: coords.lonEnd,
        }));
    }, [coords]);

    const handleChange = (e:any) => {
        const selectedFiles = Array.from(e.target.files) as File[];
        setFiles(selectedFiles);

        const newKitePaths = selectedFiles
            .filter((item: File) => item.name.includes("PowerTimeSeriesKite"))
            .map((item: File) => "OceanCurrent/" + item.name);

        if (newKitePaths.length > 0) {
            setUseApiData(prev => ({ ...prev, kite: [...prev.kite, ...newKitePaths] }));
        }
      };
    
    const handleUpload = async () => {
        if (!files || files.length === 0) return;

        const formData = new FormData();
        
        // Append files using the SAME key for all files
        files.forEach(file => {
            formData.append("files", file); // Key MUST match Flask's expected name
        });

        // Debugging: Verify FormData contents
        console.log("Files array:", files);
        for (const [key, value] of formData.entries()) {
            console.log(key, value);
          }

        const response = await api.resourceUpload(formData);

        console.log(response);
        // alert(data.message || "Upload complete!");
    }

    const handleWindDownload = async () => {
        if(useApiData.WindResolutionKm !== 2){
            const windInputGenerationApiData = {
                "WindTurbine": [],
                "ResolutionKm": useApiData.WindResolutionKm,
            };
            const windInputGenerationData = await api.generateWindBinaries(windInputGenerationApiData);
            console.log(windInputGenerationData);
    
            if (windInputGenerationData.status === 200){
                setState({load: true, value: 10})
            }
        }
        const windInputGenerationApiData = {
            "wind": useApiData.wind,
            "min_year": useApiData.start_year,
            "max_year": useApiData.end_year
        };
        const windInputGenerationData = await api.windInputGeneration(windInputGenerationApiData);
        console.log(windInputGenerationData);

        if (windInputGenerationData.status === 200){
            setState({load: true, value: 30})
        }
    };

    const handleKiteDownload = async () => {
        const kiteInputGenerationApiData = {
            "kite": useApiData.kite,
            "min_year": useApiData.start_year,
            "max_year": useApiData.end_year
        };
        const kiteInputGenerationData = await api.kiteInputGeneration(kiteInputGenerationApiData);
        console.log(kiteInputGenerationData);

        if (kiteInputGenerationData.status === 200){
            setState({load: true, value: 40})
        }
    };

    const handleWaveDownload = async () => {
        const waveInputGenerationApiData = {
            "wave": useApiData.wave,
            "min_year": useApiData.start_year,
            "max_year": useApiData.end_year
        };
        const waveInputGenerationData = await api.waveInputGeneration(waveInputGenerationApiData);
        console.log(waveInputGenerationData);

        if (waveInputGenerationData.status === 200){
            setState({load: true, value: 50})
        }
    };

    const handleOnClick = async () => {
        await handleWindDownload();

        await handleKiteDownload();

        await handleWaveDownload();

        const data = await api.portfolioOptimization(useApiData);
        console.log(data);

        setPortfolio(data.data.save_path);
        return (data.data.save_path);
    };

    const postClickHandle = async (path: string) => {
        console.log(path)
        const response = await api.portfolioPlots({portfolio: path});
        console.log(response);

        const imageBlob = new Blob([response.data], { type: 'image/png' });
        const imageURL = URL.createObjectURL(imageBlob);
        setImgSrc(imageURL);
        console.log(imageURL);
    };

    // Update all fields when dropdown changes
    const handlePresetChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        console.log("hiya!");
        const val = e.target.value;
        const range = STATE_RANGES[val];
        if (range) {
            setCoords({
                latStart: range.lat[0],
                latEnd: range.lat[1],
                lonStart: range.lon[0],
                lonEnd: range.lon[1],
            });
        }
    };

    // Update individual fields so they remain editable
    const handleInputChange = (field: keyof typeof coords, value: string) => {
        console.log("handling input change");
        setCoords(prev => ({ ...prev, [field]: parseFloat(value) || 0 }));
    };

    return (
        <div className='w-2/3 lg:w-1/3 flex flex-col items-center justify-center'>
            {state.load && (
                <div className='w-full'>
                    <span className="...">Loading: {state.value}%</span>
                    <PercentLoader width={state.value}/>
                </div>
            )}
            <div className='w-full flex flex-col justify-items-start items-start'>
            <span className="self-center text-4xl mt-5 mb-5 whitespace-nowrap align-middle h-full">Portfolio Optimization</span>
                <div className='m-3 mb-8 w-full'>
                    <p className="mb-3 not-italic underline decoration-4 underline-offset-4" style={{ textDecorationColor: colorPallete.primary }}>Resources</p>
                    <Select state={useApiData} setState={setUseApiData} />
                    <div>
                        <label
                            className="block mt-4 mb-2 text-sm font-medium text-gray-900 dark:text-white"
                            htmlFor="multiple_files"
                        >
                            Upload multiple files
                        </label>
                        <input
                            className="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400"
                            id="multiple_files"
                            type="file"
                            multiple
                            onChange={handleChange}
                        />
                        <button
                            className="inline-flex items-center w-full justify-center mt-3 px-3 py-2 text-sm font-medium text-center text-white rounded-lg hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300" style={{
                                backgroundColor: colorPallete.primary
                            }}
                            onClick={handleUpload}
                        >
                            Upload
                        </button>
                        {/* Optional: Show selected files */}
                        <ul className="mt-2">
                            {files.map((file, i) => (
                            <li key={i}>{file.name}</li>
                            ))}
                        </ul>
                    </div>
                </div>

                <div className='m-3 mb-8 w-full'>
                <p className="mb-3 not-italic underline decoration-4 underline-offset-4" style={{ textDecorationColor: colorPallete.primary }}>Location</p>
                    <label htmlFor="location-presets">Choose a preset or custom:</label>
                    <select 
                        name="location-presets" 
                        id="location-presets" 
                        onChange={handlePresetChange}
                        className="block mb-4 border p-2"
                    >
                        <option value="custom">Custom</option>
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
                    <div className='grid grid-cols-2 gap-6 justify-center'>
                        <Input 
                        label='Latitude Start' 
                        value={coords.latStart} 
                        onChange={(e) => handleInputChange('latStart', e.target.value)}
                        step="0.01" type='number' curr='deg'
                        />
                        <Input 
                        label='Latitude End' 
                        value={coords.latEnd} 
                        onChange={(e) => handleInputChange('latEnd', e.target.value)}
                        step="0.01" type='number' curr='deg'
                        />
                        <Input 
                        label='Longitude Start' 
                        value={coords.lonStart} 
                        onChange={(e) => handleInputChange('lonStart', e.target.value)}
                        step="0.01" type='number' curr='deg'
                        />
                        <Input 
                        label='Longitude End' 
                        value={coords.lonEnd} 
                        onChange={(e) => handleInputChange('lonEnd', e.target.value)}
                        step="0.01" type='number' curr='deg'
                        />
                    </div>
                </div>

                <div className='m-3 w-full'>
                <p className="mb-3 not-italic underline decoration-4 underline-offset-4" 
                style={{ textDecorationColor: colorPallete.primary }}>Technicals</p>
                    <div className='grid grid-cols-2 gap-6 justify-center'>
                        <TransmissionCapSelect state={useApiData} setState={setUseApiData}/>
                        <Input label='Max Trans. System Radius' type='number' step="0.01" placeholder='30' curr='mi' state={useApiData} setState={setUseApiData}/>
                        {useApiData.wind.length > 0 && (<Input label='Number of Wind Devices / Resource' type='number' step="1" placeholder='4' curr='' state={useApiData} setState={setUseApiData}/>)}
                        {useApiData.wind.length > 0 && (<Input label='Number of Wind Devices / sq. km' step="1" type='number' placeholder='2' curr='' state={useApiData} setState={setUseApiData}/>)}

                        {useApiData.kite.length > 0 && (<Input label='Number of Kite Devices / Resource' type='number' step="1" placeholder='390' curr='' state={useApiData} setState={setUseApiData}/>)}
                        {useApiData.kite.length > 0 && (<Input label='Number of Kite Devices / sq. km' step="1" type='number' placeholder='0' curr='' state={useApiData} setState={setUseApiData}/>)}

                        {useApiData.wave.length > 0 && (<Input label='Number of Wave Devices / Resource' type='number' step="1" placeholder='300' curr='' state={useApiData} setState={setUseApiData}/>)}
                        {useApiData.wave.length > 0 && (<Input label='Number of Wave Devices / sq. km' step="1" type='number' placeholder='0' curr='' state={useApiData} setState={setUseApiData}/>)}

                        {useApiData.coaxial.length > 0 && (<Input label='Number of Coaxial Devices / Resource' type='number' step="1" placeholder='390' curr='' state={useApiData} setState={setUseApiData}/>)}
                        {useApiData.coaxial.length > 0 && (<Input label='Number of Coaxial Devices / sq. km' step="1" type='number' placeholder='0' curr='' state={useApiData} setState={setUseApiData}/>)}

                        {/* <Input label='Year(s) of Analysis' type='number' step="1" placeholder='0' curr=''/> */}
                        <YearSelect label='Year(s) of Analysis from' state={useApiData} setState={setUseApiData} start={true} />
                        <YearSelect label='Year(s) of Analysis to' state={useApiData} setState={setUseApiData} start={false} />
                        <Input label='Distance from Shore' step="0.01" type='number' placeholder='0.0' curr='mi' state={useApiData} setState={setUseApiData}/>
                        <Input label='Max Water Depth' type='number' step="0.01" placeholder='0.0' curr='mi'state={useApiData} setState={setUseApiData}/>
                        
                        <Input label='LCOE Min' type='number' step="1" placeholder='100' curr='$/MWh' state={useApiData} setState={setUseApiData}/>
                        <Input label='LCOE Max' type='number' step="1" placeholder='120' curr='$/MWh'state={useApiData} setState={setUseApiData}/>
                        <Input label='LCOE Step Size' type='number' step="1" placeholder='2' curr='' state={useApiData} setState={setUseApiData}/>
                    </div>
                </div>
                <button onClick={async () => {
                    setState({load: true, value: 0})
          const path = await handleOnClick();
          setState({load: false, value: 100})
          await postClickHandle(path);
                }} className="inline-flex items-center w-full justify-center m-3 mt-8 px-3 py-2 text-sm font-medium text-center text-white rounded-lg hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300" style={{
                    backgroundColor: colorPallete.primary
                }}>Generate Efficient Frontiers</button>
            </div>
            <img id='image' src={imgSrc} className='w-full h-full' />
        </div>
    );
};

export default Prototype;
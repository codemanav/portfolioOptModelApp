import React from 'react';

interface InputProps {
    label: string;
    type: string;
    placeholder?: string;
    curr: string;
    step: string;
    // Updated state type to include the missing keys like max_system_radius
    state?: any; 
    setState?: any;
    value?: string | number; // This is the most important prop for presets
    onChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

const Input = (props: InputProps) => {
    // Mapping labels to state keys to clean up the logic
    const labelMap: Record<string, string> = {
        "LCOE Min": "lcoe_min",
        "LCOE Max": "lcoe_max",
        "LCOE Step Size": "lcoe_step",
        "Max Trans. System Radius": "max_system_radius",
        "Number of Wind Devices / Resource": "WindTurbinesPerSite",
        "Number of Wind Devices / sq. km": "WindResolutionKm",
        "Number of Wave Devices / Resource": "WaveTurbinesPerSite",
        "Number of Kite Devices / Resource": "KiteTurbinesPerSite",
        "Number of Coaxial Devices / Resource": "CoaxialTurbinesPerSite",
        "Distance from Shore": "distance_from_shore", // Ensure these match your state
        "Max Water Depth": "max_water_depth"
    };

    const key = labelMap[props.label];
    const resolvedValue = props.value !== undefined
        ? props.value
        : (props.state && key) ? props.state[key] : "";

    const onChangeHandler = (event: React.ChangeEvent<HTMLInputElement>) => {
        const rawValue = event.target.value;
        // 1. Trigger the coordinate change handler if passed (Location fields)
        if (props.onChange) {
            props.onChange(event);
        }

        // 2. Trigger the generic state logic if passed (Technical fields)
        if (props.state && props.setState) {
            const key = labelMap[props.label];
            if (key) {
                // Convert to number, but if it's empty, use 0
                // Using Number() helps strip leading zeros when the state updates
                const numValue = rawValue === "" ? 0 : Number(rawValue);
                props.setState({
                    ...props.state,
                    [key]: numValue
                });
            }
        }
    };

    return (
        <div className="w-full">
            <label className="block text-sm/6 font-medium text-gray-900">
                {props.label}
            </label>
            <div className="mt-2">
                <div className="flex items-center rounded-md bg-white pl-3 outline outline-1 -outline-offset-1 outline-gray-300 focus-within:outline focus-within:outline-2 focus-within:-outline-offset-2 focus-within:outline-indigo-600">
                    <input
                        type={props.type}
                        step={props.step}
                        placeholder={props.placeholder}
                        // Convert to Number and back to String to strip leading zeros
                        // but only if it's not empty (to allow backspacing)
                        value={resolvedValue === "" ? "" : Number(resolvedValue).toString()}
                        onChange={onChangeHandler}
                        className="block min-w-0 grow py-1.5 pr-3 pl-1 text-base text-gray-900 focus:outline-none sm:text-sm/6 rounded-md"
                    />
                    <div className="grid shrink-1 grid-cols-1">
                        <span className="col-start-1 row-start-1 py-1.5 pr-7 pl-3 text-base text-gray-500 sm:text-sm/6">
                            {props.curr}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Input;
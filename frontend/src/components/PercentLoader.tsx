import React from 'react';

interface PercentLoaderInterface {
    width: number
};

const PercentLoader = (props: PercentLoaderInterface) => {
    return (
        <div className="w-full h-full bg-gray-400 rounded-full h-2.5 dark:bg-gray-700">
            <div className="bg-blue-600 h-2.5 rounded-full" style={{"width": `${props.width}%`}}></div>
        </div>
    );
};

export default PercentLoader
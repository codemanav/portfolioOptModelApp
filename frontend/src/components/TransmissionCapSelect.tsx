import { useEffect, useState } from 'react';

interface DesignOption {
  name: string;
  label: string;
  path: string;
  capacity_mw?: number;
}

interface TransmissionCapSelectProps {
  available: DesignOption[];
  selected: string;
  onSelect: (path: string) => void;
}

export default function TransmissionCapSelect(props: TransmissionCapSelectProps) {
  const { available, selected, onSelect } = props;

  // Auto-select the first option if nothing is selected and options exist
  useEffect(() => {
    if (!selected && available.length > 0) {
      onSelect(available[0].path);
    }
  }, [available]);

  if (available.length === 0) {
    return (
      <div>
        <label className="block mb-2 text-sm font-medium text-gray-900">
          Transmission Capacity
        </label>
        <p className="text-sm text-gray-400 italic">No transmission data for this state</p>
      </div>
    );
  }

  return (
    <div>
      <label htmlFor="transmission-select" className="block mb-2 text-sm font-medium text-gray-900">
        Transmission Capacity
      </label>
      <select
        id="transmission-select"
        className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5"
        value={selected}
        onChange={(e) => onSelect(e.target.value)}
      >
        {available.map(opt => (
          <option key={opt.path} value={opt.path}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

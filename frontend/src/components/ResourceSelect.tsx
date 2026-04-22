import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/react'
import { ChevronDownIcon } from '@heroicons/react/20/solid'
import { colorPallete } from '@/styles/constants'

/**
 * Each design option returned by /availableData has:
 *   name:  internal identifier (e.g. "ATB_18MW_2030")
 *   label: human-readable (e.g. "18MW 2030")
 *   path:  absolute file path on the server
 */
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

interface ResourceSelectProps {
  available: AvailableData;
  selectedWind: string[];
  selectedWave: string[];
  selectedKite: string[];
  onToggle: (tech: 'wind' | 'wave' | 'kite', path: string) => void;
}

export default function ResourceSelect(props: ResourceSelectProps) {
  const { available, selectedWind, selectedWave, selectedKite, onToggle } = props;

  const resourceGroups: { label: string; key: 'wind' | 'kite' | 'wave'; designs: DesignOption[] }[] = [
    { label: 'Wind',    key: 'wind',    designs: available.wind },
    { label: 'Kite',    key: 'kite',    designs: available.kite },
    { label: 'Wave',    key: 'wave',    designs: available.wave },
  ];

  const selectedMap: Record<string, string[]> = {
    wind: selectedWind,
    wave: selectedWave,
    kite: selectedKite,
  };

  const totalSelected = selectedWind.length + selectedWave.length + selectedKite.length;

  return (
    <Menu as="div" className="relative inline-block text-left">
      <div>
        <MenuButton className="inline-flex justify-center gap-x-1.5 rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 ring-1 shadow-xs ring-gray-300 ring-inset hover:bg-gray-50">
          Resources{totalSelected > 0 ? ` (${totalSelected} selected)` : ''}
          <ChevronDownIcon aria-hidden="true" className="-mr-1 size-5 text-gray-400" />
        </MenuButton>
      </div>

      <MenuItems
        transition
        className="absolute z-10 mt-2 p-4 mx-auto origin-top-right rounded-md bg-white ring-1 shadow-lg ring-black/5 transition focus:outline-hidden data-closed:scale-95 data-closed:transform data-closed:opacity-0 data-enter:duration-100 data-enter:ease-out data-leave:duration-75 data-leave:ease-in grid place-content-center py-8"
      >
        {resourceGroups.map(({ label, key, designs }) => {
          if (designs.length === 0) return null;
          return (
            <div key={key}>
              <p className="mt-5 text-sm not-italic mb-1" style={{ textDecorationColor: colorPallete.primary }}>
                {label}
              </p>
              <div className='w-full h-0.5 mb-2' style={{ backgroundColor: colorPallete.primary }} />
              <div className="grid grid-cols-3 gap-x-8 gap-y-2 grid-flow-row">
                {designs.map(design => (
                  <div className="flex" key={design.path}>
                    <input
                      type="checkbox"
                      className="shrink-0 mt-0.5 border-gray-200 rounded text-blue-600 focus:ring-blue-500 disabled:opacity-50 disabled:pointer-events-none"
                      id={design.path}
                      checked={selectedMap[key].includes(design.path)}
                      onChange={() => onToggle(key, design.path)}
                    />
                    <label htmlFor={design.path} className="text-sm text-gray-500 ms-3">
                      {design.label}
                    </label>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
        {available.wind.length === 0 && available.wave.length === 0 && available.kite.length === 0 && (
          <p className="text-sm text-gray-400 italic py-4">
            No pre-computed data found for this state. Select a state with available data or upload resource files.
          </p>
        )}
      </MenuItems>
    </Menu>
  )
}

import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/react'
import { ChevronDownIcon } from '@heroicons/react/20/solid'
import { colorPallete } from '@/styles/constants'

interface ResourceSelectInterface {
  state: {
    wind: string[],
    wave: string[],
    kite: string[],
    coaxial: string[],
    transmission: string[],
    lcoe_max: number,
    lcoe_min: number,
    lcoe_step: number,
    start_year: number,
    end_year: number,
  };
  setState: any;
};

export default function ResourceSelect(props: ResourceSelectInterface) {
  const windDesigns = [ "8MW Vestas 2020", "12MW 2030", "15MW 2030", "18MW 2030" ];
  const kiteDesigns = [ "0.05MW (0.5m/s)", "0.14MW (0.75m/s)", "0.31MW (1.0m/s)", "0.57MW (1.25m/s)", "0.93MW (1.5m/s)", "1.43MW (1.75m/s)", "2.04MW (2.0m/s)", "1.987MW (2.25m/s)", "1.87MW (2.5m/s)", "1.81MW (2.75m/s)" ];
  const waveDesigns = [ "Pelamis", "RM3" ];
  const coaxialDesigns = [ "0.6MW (1.0m/s)", "1.0MW (1.5m/s)", "1.75MW (1.75m/s)", "2.0MW (1.75m/s)", "1.5MW (1.5m/s)" ];

  interface dictInterface {
    [key: string]:string
  };

  const dict: dictInterface = {
    "8MW Vestas 2020": `Wind/Upscale3h_0.1Degree_${props.state.start_year}_${props.state.end_year}_GenCost_ATB_8MW_2020_Vestas.npz`,
    "12MW 2030": `Wind/Upscale3h_0.1Degree_${props.state.start_year}_${props.state.end_year}_GenCost_ATB_12MW_2030.npz`, 
    "15MW 2030": `Wind/Upscale3h_0.1Degree_${props.state.start_year}_${props.state.end_year}_GenCost_ATB_15MW_2030.npz`, 
    "18MW 2030": `Wind/Upscale3h_0.1Degree_${props.state.start_year}_${props.state.end_year}_GenCost_ATB_18MW_2030.npz`,
    "0.05MW (0.5m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS0.5_${props.state.start_year}_${props.state.end_year}.npz`,
    "0.14MW (0.75m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS0.75_${props.state.start_year}_${props.state.end_year}.npz`,
    "0.31MW (1.0m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS1.0_${props.state.start_year}_${props.state.end_year}.npz`,
    "0.57MW (1.25m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS1.25_${props.state.start_year}_${props.state.end_year}.npz`,
    "0.93MW (1.5m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS1.5_${props.state.start_year}_${props.state.end_year}.npz`,
    "1.43MW (1.75m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS1.75_${props.state.start_year}_${props.state.end_year}.npz`,
    "2.04MW (2.0m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS2.0_${props.state.start_year}_${props.state.end_year}.npz`,
    "1.987MW (2.25m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS2.25_${props.state.start_year}_${props.state.end_year}.npz`,
    "1.87MW (2.5m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS2.5_${props.state.start_year}_${props.state.end_year}.npz`,
    "1.81MW (2.75m/s)": `OceanCurrent/PowerTimeSeriesKite_VD50_BCS2.75_${props.state.start_year}_${props.state.end_year}.npz`,
    "Pelamis": `Wave/${props.state.start_year}_${props.state.end_year}_Pelamis.npz`,
    "RM3": `Wave/${props.state.start_year}_${props.state.end_year}_RM3.npz`,
    "0.6MW (1.0m/s)": "",
  };

  const transmissionSystem = [ '1.2GW', '1.0GW', '0.6GW', '0.3GW', '0.1GW' ];

  const resourceGroups: {label: string; key: 'wind' | 'kite' | 'wave' | 'coaxial'; designs: string[] }[] = [
    { label: 'Wind',    key: 'wind',    designs: windDesigns },
    { label: 'Kite',    key: 'kite',    designs: kiteDesigns },
    { label: 'Wave',    key: 'wave',    designs: waveDesigns },
    { label: 'Coaxial', key: 'coaxial', designs: coaxialDesigns },
  ];

  const handleToggle = (key: 'wind' | 'kite' | 'wave' | 'coaxial', val: string) => {
    const current: string[] = props.state[key];
    const path = dict[val];
    const updated = current.includes(path)
      ? current.filter(e => e !== path)
      : [...current, path];
    props.setState({ ...props.state, [key]: updated });
  };

  return (
    <Menu as="div" className="relativeinline-block text-left">
      <div>
        <MenuButton className="inline-flex justify-center gap-x-1.5 rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 ring-1 shadow-xs ring-gray-300 ring-inset hover:bg-gray-50">
          Options
          <ChevronDownIcon aria-hidden="true" className="-mr-1 size-5 text-gray-400" />
        </MenuButton>
      </div>

      <MenuItems
        transition
        className="absolute z-10 mt-2 p-4 mx-auto origin-top-right rounded-md bg-white ring-1 shadow-lg ring-black/5 transition focus:outline-hidden data-closed:scale-95 data-closed:transform data-closed:opacity-0 data-enter:duration-100 data-enter:ease-out data-leave:duration-75 data-leave:ease-in grid place-content-center py-8"
      >
        {resourceGroups.map(({ label, key, designs }) => (
        <div key={key}>
          <p className="mt-5 text-sm not-italic mb-1" style={{ textDecorationColor: colorPallete.primary }}>
            {label}
          </p>
          <div className='w-full h-0.5 mb-2' style={{ backgroundColor: colorPallete.primary }} />
          <div className="grid grid-cols-3 gap-x-8 gap-y-2 grid-flow-row">
            {designs.map(elem => (
              <div className="flex" key={elem}>
                <input
                  type="checkbox"
                  className="shrink-0 mt-0.5 border-gray-200 rounded text-blue-600 focus:ring-blue-500 disabled:opacity-50 disabled:pointer-events-none dark:bg-neutral-800 dark:border-neutral-700 dark:checked:bg-blue-500 dark:checked:border-blue-500 dark:focus:ring-offset-gray-800"
                  id={elem}
                  checked={props.state[key].includes(dict[elem])}
                  onChange={() => handleToggle(key, elem)}
                />
                <label htmlFor={elem} className="text-sm text-gray-500 ms-3 dark:text-neutral-400">
                  {elem}
                </label>
              </div>
            ))}
          </div>
        </div>
      ))}
          {/* TRANSMISSION CAPACITY SYSTEMS */}
        {/* <p className="mt-5 text-sm not-italic" style={{ textDecorationColor: colorPallete.primary }}>Transmission System Capacity</p>
        <div className='w-full h-0.5 mb-2' style={{ backgroundColor: colorPallete.primary }}></div>
        <div className="grid grid-cols-3 gap-x-8 gap-y-2 grid-flow-row">
          {transmissionSystem.map(elem => {
            return <div className="flex" key={elem}>
            <input type="checkbox" className="shrink-0 mt-0.5 border-gray-200 rounded text-blue-600 focus:ring-blue-500 disabled:opacity-50 disabled:pointer-events-none dark:bg-neutral-800 dark:border-neutral-700 dark:checked:bg-blue-500 dark:checked:border-blue-500 dark:focus:ring-offset-gray-800" id={elem} />
            <label htmlFor={elem} className="text-sm text-gray-500 ms-3 dark:text-neutral-400">{elem}</label>
          </div>
          })}
        </div> */}
      </MenuItems>
    </Menu>
  )
}


// 'use client'

// import { useState } from 'react'
// import { Label, Listbox, ListboxButton, ListboxOption, ListboxOptions } from '@headlessui/react'
// import { ChevronUpDownIcon } from '@heroicons/react/16/solid'
// import { CheckIcon } from '@heroicons/react/20/solid'

// import { WIND_ENERGY, WAVE_ENERGY, KITE_ENERGY, OCEAN_ENERGY } from '../constants/names';

// const list = [
//     {
//         id: 1,
//         label: 'Wind Energy',
//         value: WIND_ENERGY
//     },
//     {
//         id: 2,
//         label: 'Wave Energy',
//         value: WAVE_ENERGY
//     },
//     {
//         id: 3,
//         label: 'Kite Energy',
//         value: KITE_ENERGY
//     },
//     {
//         id: 4,
//         label: 'Ocean Energy',
//         value: OCEAN_ENERGY
//     }
// ];

// const ResourceSelect = () => {
//   const [selected, setSelected] = useState(list[1])

//   return (
//     <Listbox value={selected} onChange={setSelected}>
//       <Label className="block text-sm/6 font-medium text-gray-900">Resource Type</Label>
//       <div className="relative mt-2 w-full">
//         <ListboxButton className="grid w-full cursor-default grid-cols-1 rounded-md bg-white py-1.5 pl-3 pr-2 text-left text-gray-900 outline outline-1 -outline-offset-1 outline-gray-300 focus:outline focus:outline-2 focus:-outline-offset-2 focus:outline-indigo-600 sm:text-sm/6">
//           <span className="col-start-1 row-start-1 flex items-center gap-3 pr-6">
//             <span className="block truncate">{selected.label}</span>
//           </span>
//           <ChevronUpDownIcon
//             aria-hidden="true"
//             className="col-start-1 row-start-1 size-5 self-center justify-self-end text-gray-500 sm:size-4"
//           />
//         </ListboxButton>

//         <ListboxOptions
//           transition
//           className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black/5 focus:outline-none data-[closed]:data-[leave]:opacity-0 data-[leave]:transition data-[leave]:duration-100 data-[leave]:ease-in sm:text-sm"
//         >
//           {list.map((elem) => (
//             <ListboxOption
//               key={elem.id}
//               value={elem}
//               className="group relative cursor-default select-none py-2 pl-3 pr-9 text-gray-900 data-[focus]:bg-indigo-600 data-[focus]:text-white data-[focus]:outline-none"
//             >
//               <div className="flex items-center">
  
//                 <span className="ml-3 block truncate font-normal group-data-[selected]:font-semibold">
//                   {elem.label}
//                 </span>
//               </div>

//               <span className="absolute inset-y-0 right-0 flex items-center pr-4 text-indigo-600 group-[&:not([data-selected])]:hidden group-data-[focus]:text-white">
//                 <CheckIcon aria-hidden="true" className="size-5" />
//               </span>
//             </ListboxOption>
//           ))}
//         </ListboxOptions>
//       </div>
//     </Listbox>
//   )
// }

// export default ResourceSelect;
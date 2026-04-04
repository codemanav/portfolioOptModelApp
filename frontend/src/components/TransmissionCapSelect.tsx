'use client'

import { useState, useEffect } from 'react'
import { Label, Listbox, ListboxButton, ListboxOption, ListboxOptions } from '@headlessui/react'
import { ChevronUpDownIcon } from '@heroicons/react/16/solid'
import { CheckIcon } from '@heroicons/react/20/solid'

import { WIND_ENERGY, WAVE_ENERGY, KITE_ENERGY, OCEAN_ENERGY } from '../constants/names';

interface TransmissionCapSelectInterface {
    state: {
      wind: string[],
      wave: string[],
      kite: string[],
      transmission: string[],
      lcoe_max: number,
      lcoe_min: number,
      lcoe_step: number,
      start_year: number,
      end_year: number,
    };
    setState: any;
  };

const list = [
    {
        id: 1,
        label: '300 MW',
        value: 'Transmission/Transmission_300MW.npz'
    },
    {
        id: 2,
        label: '600 MW',
        value: 'Transmission/Transmission_600MW.npz'
    },
    {
        id: 3,
        label: '1000 MW',
        value: 'Transmission/Transmission_1000MW.npz'
    },
    {
        id: 4,
        label: '1200 MW',
        value: 'Transmission/Transmission_1200MW.npz'
    }
];

const TransmissionCapSelect = (props: TransmissionCapSelectInterface) => {
  const [selected, setSelected] = useState(list[0])

  useEffect(() => {
        props.setState({...props.state, transmission: [selected.value]})
  }, [selected]);

  return (
    <Listbox value={selected} onChange={setSelected}>
        <div>
        <Label className="block text-sm/6 font-medium text-gray-900">Transmission Capacity</Label>
        <div className="relative mt-2 w-full">
            <ListboxButton className="grid w-full cursor-default grid-cols-1 rounded-md bg-white py-1.5 pl-3 pr-2 text-left text-gray-900 outline outline-1 -outline-offset-1 outline-gray-300 focus:outline focus:outline-2 focus:-outline-offset-2 focus:outline-indigo-600 sm:text-sm/6">
            <span className="col-start-1 row-start-1 flex items-center gap-3 pr-6">
                {/* <img alt="" src={""} className="size-5 shrink-0 rounded-full" /> */}
                <span className="block truncate">{selected.label}</span>
            </span>
            <ChevronUpDownIcon
                aria-hidden="true"
                className="col-start-1 row-start-1 size-5 self-center justify-self-end text-gray-500 sm:size-4"
            />
            </ListboxButton>

            <ListboxOptions
            transition
            className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black/5 focus:outline-none data-[closed]:data-[leave]:opacity-0 data-[leave]:transition data-[leave]:duration-100 data-[leave]:ease-in sm:text-sm"
            >
            {list.map((elem) => (
                <ListboxOption
                key={elem.id}
                value={elem}
                className="group relative cursor-default select-none py-2 pl-3 pr-9 text-gray-900 data-[focus]:bg-indigo-600 data-[focus]:text-white data-[focus]:outline-none"
                >
                <div className="flex items-center">
                    {/* <img alt="" src={""} className="size-5 shrink-0 rounded-full" /> */}
                    <span className="ml-3 block truncate font-normal group-data-[selected]:font-semibold">
                    {elem.label}
                    </span>
                </div>

                <span className="absolute inset-y-0 right-0 flex items-center pr-4 text-indigo-600 group-[&:not([data-selected])]:hidden group-data-[focus]:text-white">
                    <CheckIcon aria-hidden="true" className="size-5" />
                </span>
                </ListboxOption>
            ))}
            </ListboxOptions>
        </div>
    </div>
    </Listbox>
  )
}

export default TransmissionCapSelect;
import Image from 'next/image';
import { colorPallete } from '@/styles/constants';

const WindAbout = () => {
    const turbineSpecs = [
        { mw: '8 MW',  year: '2021 Design', diameter: 'D159m', hub: 'H102m' },
        { mw: '12 MW', year: '2030 Design', diameter: 'D214m', hub: 'H136m' },
        { mw: '15 MW', year: '2030 Design', diameter: 'D240m', hub: 'H150m' },
        { mw: '18 MW', year: '2030 Design', diameter: 'D263m', hub: 'H161m' },
    ];

    return (
        <div className='w-2/3 lg:w-1/2 flex flex-col items-start mx-auto py-10'>
            <h1 className='text-4xl font-bold mb-6' style={{ color: 'var(--foreground)' }}>Wind Energy</h1>

            <p className='mb-6 leading-relaxed' style={{ color: 'var(--muted)' }}>
                This work uses reliable wind turbine models from the NREL 2023 Annual Technology
                Baseline (ATB) [1]. Models for 8 MW turbines (typical 2021 design) and 12, 15, and
                18 MW turbines which are estimated to represent offshore wind deployments in 2030,
                considering respectively a conservative, moderate, and advanced development of the
                offshore wind energy sector. These wind turbines are shown in Figure 1 along with
                their associated rotor diameters and hub heights.
            </p>

            {/* Turbine specs table */}
            <div className='w-full mb-6 overflow-x-auto rounded-xl' style={{ border: '1px solid var(--border)' }}>
                <table className='w-full text-sm text-left'>
                    <thead>
                        <tr style={{ backgroundColor: colorPallete.primary }}>
                            <th className='p-3 text-white font-semibold'>Design</th>
                            <th className='p-3 text-white font-semibold'>Capacity</th>
                            <th className='p-3 text-white font-semibold'>Rotor Diameter</th>
                            <th className='p-3 text-white font-semibold'>Hub Height</th>
                        </tr>
                    </thead>
                    <tbody>
                        {turbineSpecs.map((t, i) => (
                            <tr
                                key={t.mw}
                                style={{
                                    backgroundColor: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-2)',
                                    borderTop: '1px solid var(--border)',
                                }}
                            >
                                <td className='p-3' style={{ color: 'var(--foreground)' }}>{t.year}</td>
                                <td className='p-3' style={{ color: 'var(--foreground)' }}>{t.mw}</td>
                                <td className='p-3' style={{ color: 'var(--muted)' }}>{t.diameter}</td>
                                <td className='p-3' style={{ color: 'var(--muted)' }}>{t.hub}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <figure className='w-full mb-8 flex flex-col items-center'>
                <Image src='/wind/wind_turbines.png' alt='Wind turbine designs' width={600} height={400} />
                <figcaption className='text-sm italic mt-2' style={{ color: 'var(--muted)' }}>
                    Figure 1: 8, 12, 15, and 18 MW turbine designs from [1] with associated hub heights and diameters
                </figcaption>
            </figure>

            <p className='mb-4 leading-relaxed' style={{ color: 'var(--muted)' }}>
                To solve for the power the wind turbines produce at a given wind speed, power is
                calculated based on the power law:
            </p>

            {/* Power equation */}
            <div
                className='w-full flex justify-center my-4 p-4 rounded-xl'
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
                <p className='text-lg font-medium' style={{ color: 'var(--foreground)' }}>
                    P = &frac12;&rho;AC<sub>p</sub>v<sub>w</sub><sup>3</sup>
                </p>
            </div>

            <p className='mb-2' style={{ color: 'var(--muted)' }}>Where:</p>
            <ul className='mb-6 ml-4 list-disc space-y-1' style={{ color: 'var(--muted)' }}>
                <li><strong style={{ color: 'var(--foreground)' }}>&rho;</strong> &mdash; air density</li>
                <li><strong style={{ color: 'var(--foreground)' }}>A</strong> &mdash; swept area of the wind turbine blades</li>
                <li><strong style={{ color: 'var(--foreground)' }}>C<sub>p</sub></strong> &mdash; coefficient of power of the turbine</li>
                <li><strong style={{ color: 'var(--foreground)' }}>v<sub>w</sub></strong> &mdash; wind speed at hub height</li>
            </ul>

            <figure className='w-full mb-8 flex flex-col items-center'>
                <Image src='/wind/wind_power_curves.png' alt='Wind turbine power curves' width={600} height={400} />
                <figcaption className='text-sm italic mt-2' style={{ color: 'var(--muted)' }}>
                    Figure 2: 8, 12, 15, 18 MW wind turbine power curves from [1]
                </figcaption>
            </figure>

            {/* Citation */}
            <div className='w-full mt-4 pt-4' style={{ borderTop: '1px solid var(--border)' }}>
                <p className='text-sm font-semibold mb-2' style={{ color: 'var(--muted)' }}>References</p>
                <p className='text-sm' style={{ color: 'var(--muted)' }}>
                    [1] Annual Technology Baseline, Tech. rep., National Renewable Energy Laboratory,
                    [Online; accessed June 2023] (2022).
                </p>
                <p className='text-sm mt-2' style={{ color: 'var(--muted)' }}>
                    M. Maceda et al., &ldquo;Fused portfolio optimization for Harnessing Marine Renewable
                    Energy Resources,&rdquo; <em>Energy</em>, vol. 342, p. 139660, Jan. 2026.{' '}
                    <a
                        href='https://www.sciencedirect.com/science/article/pii/S0360544225053022'
                        className='underline hover:opacity-70'
                        style={{ color: colorPallete.primary }}
                        target='_blank'
                        rel='noopener noreferrer'
                    >
                        doi:10.1016/j.energy.2025.139660
                    </a>
                </p>
            </div>
        </div>
    );
}

export default WindAbout;

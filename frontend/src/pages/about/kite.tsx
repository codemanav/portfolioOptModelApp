import Image from 'next/image';
import { colorPallete } from '@/styles/constants';

const KiteAbout = () => {
    const kiteSpecs = [
        { speed: '0.50', power: '53.7',   mass: '1780.6', span: '11.0', ar: '5.3' },
        { speed: '0.75', power: '147.5',  mass: '2442.2', span: '11.0', ar: '4.6' },
        { speed: '1.00', power: '312.6',  mass: '3262.0', span: '11.0', ar: '3.8' },
        { speed: '1.25', power: '570.8',  mass: '3738.6', span: '11.0', ar: '3.8' },
        { speed: '1.50', power: '931.9',  mass: '4822.5', span: '11.0', ar: '3.0' },
        { speed: '1.75', power: '1431.6', mass: '5248.7', span: '11.0', ar: '3.0' },
        { speed: '2.00', power: '2041.2', mass: '5682.4', span: '11.0', ar: '3.0' },
        { speed: '2.25', power: '1987.7', mass: '4063.3', span: '9.7',  ar: '3.0' },
        { speed: '2.50', power: '1872.0', mass: '2784.8', span: '8.3',  ar: '3.0' },
        { speed: '2.75', power: '1814.4', mass: '2101.5', span: '7.4',  ar: '3.0' },
    ];

    return (
        <div className='w-2/3 lg:w-1/2 flex flex-col items-start mx-auto py-10'>
            <h1 className='text-4xl font-bold mb-6' style={{ color: 'var(--foreground)' }}>Marine Hydrokinetic Kites</h1>

            <p className='mb-6 leading-relaxed' style={{ color: 'var(--muted)' }}>
                Marine hydrokinetic kites are the leading technology for harvesting tidal and ocean
                current energy, and are currently commercially deployed by Minesto [1]. Their high
                lift-to-drag ratio allows them to fly underwater in specific patterns perpendicular
                to the oncoming flow, enabling them to achieve speeds significantly in excess of the
                prevailing flow speed. Through the cubic relationship between flight speed and power,
                this leads to an order of magnitude increase in power per unit area compared to
                stationary systems [2].
            </p>

            <Image
                src='/kite/kite_deployment.png'
                alt='Deployment of an MHK kite from a floating platform'
                width={600}
                height={400}
                className='w-full mb-8 rounded-xl'
            />

            <h2 className='text-2xl font-semibold mb-4' style={{ color: 'var(--foreground)' }}>Optimization Model</h2>

            <p className='mb-4 leading-relaxed' style={{ color: 'var(--muted)' }}>
                A family of kite designs and corresponding performance characterizations were
                generated using an in-house model and optimization procedure. Each kite was
                optimized to maximize power output at a given rated flow speed, subject to
                structural and buoyancy constraints:
            </p>

            <div
                className='w-full flex flex-col items-center my-4 p-5 rounded-xl'
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
                <p className='text-lg font-medium mb-2' style={{ color: 'var(--foreground)' }}>
                    maximize P(u, v<sub>r</sub>)
                </p>
                <p className='text-base' style={{ color: 'var(--muted)' }}>
                    subject to: h(u, v<sub>r</sub>) = 0
                </p>
                <p className='text-base' style={{ color: 'var(--muted)' }}>
                    g(u, v<sub>r</sub>) &le; 0
                </p>
            </div>

            <p className='mb-2' style={{ color: 'var(--muted)' }}>Where:</p>
            <ul className='mb-6 ml-4 list-disc space-y-1' style={{ color: 'var(--muted)' }}>
                <li><strong style={{ color: 'var(--foreground)' }}>P</strong> &mdash; power output</li>
                <li><strong style={{ color: 'var(--foreground)' }}>u</strong> &mdash; vector of design variables (wingspan, aspect ratio, fuselage diameter, fuselage length, shell thickness, spar thickness, fuselage thickness)</li>
                <li><strong style={{ color: 'var(--foreground)' }}>v<sub>r</sub></strong> &mdash; rated flow speed</li>
                <li><strong style={{ color: 'var(--foreground)' }}>h(u, v<sub>r</sub>)</strong> &mdash; equality constraints (fuselage thickness for shear stress and bending moment)</li>
                <li><strong style={{ color: 'var(--foreground)' }}>g(u, v<sub>r</sub>)</strong> &mdash; inequality constraints (neutral buoyancy, wing tip deflection)</li>
            </ul>

            <h2 className='text-2xl font-semibold mb-4' style={{ color: 'var(--foreground)' }}>Kite Designs</h2>

            <p className='mb-4 leading-relaxed' style={{ color: 'var(--muted)' }}>
                The optimization was solved for rated flow speeds from 0.5 m/s to 2.75 m/s in
                increments of 0.25 m/s. The resulting designs are summarized in Table 1 below.
            </p>

            <div className='w-full mb-4 overflow-x-auto rounded-xl' style={{ border: '1px solid var(--border)' }}>
                <table className='w-full text-sm text-left'>
                    <thead>
                        <tr style={{ backgroundColor: colorPallete.primary }}>
                            <th className='p-3 text-white font-semibold'>Rated Flow Speed (m/s)</th>
                            <th className='p-3 text-white font-semibold'>Power Output (kW)</th>
                            <th className='p-3 text-white font-semibold'>Structural Mass (kg)</th>
                            <th className='p-3 text-white font-semibold'>Span (m)</th>
                            <th className='p-3 text-white font-semibold'>Aspect Ratio</th>
                        </tr>
                    </thead>
                    <tbody>
                        {kiteSpecs.map((k, i) => (
                            <tr
                                key={k.speed}
                                style={{
                                    backgroundColor: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-2)',
                                    borderTop: '1px solid var(--border)',
                                }}
                            >
                                <td className='p-3' style={{ color: 'var(--foreground)' }}>{k.speed}</td>
                                <td className='p-3' style={{ color: 'var(--foreground)' }}>{k.power}</td>
                                <td className='p-3' style={{ color: 'var(--muted)' }}>{k.mass}</td>
                                <td className='p-3' style={{ color: 'var(--muted)' }}>{k.span}</td>
                                <td className='p-3' style={{ color: 'var(--muted)' }}>{k.ar}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <p className='text-sm italic mb-8' style={{ color: 'var(--muted)' }}>
                Table 1: Power outputs, structural masses, spans, and aspect ratios of the optimized kite designs
            </p>

            <div className='w-full mt-4 pt-4' style={{ borderTop: '1px solid var(--border)' }}>
                <p className='text-sm font-semibold mb-2' style={{ color: 'var(--muted)' }}>References</p>
                <p className='text-sm' style={{ color: 'var(--muted)' }}>
                    [1] Projects, Minesto, [Online; accessed February 2025] (2025).{' '}
                    <a
                        href='https://minesto.com/projects/'
                        className='underline hover:opacity-70'
                        style={{ color: colorPallete.primary }}
                        target='_blank'
                        rel='noopener noreferrer'
                    >
                        https://minesto.com/projects/
                    </a>
                </p>
                <p className='text-sm mt-2' style={{ color: 'var(--muted)' }}>
                    [2] M. L. Loyd, &ldquo;Crosswind kite power (for large-scale wind power production),&rdquo;{' '}
                    <em>Journal of Energy</em>, vol. 4, no. 3, pp. 106&ndash;111, 1980.
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

export default KiteAbout;

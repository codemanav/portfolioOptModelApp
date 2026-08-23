import Link from 'next/link';
import about from '../static/about';

const About = () => {
    const [featured, ...rest] = about;

    return (
        <div className="max-w-5xl mx-auto w-full px-4 py-12">

            {/* Page header */}
            <div className="mb-10">
                <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--foreground)' }}>
                    Technologies
                </h1>
                <p className="text-sm" style={{ color: 'var(--muted)' }}>
                    Explore the renewable energy technologies modelled in the portfolio optimizer.
                </p>
            </div>

            {/* Featured card — horizontal, full width */}
            <div
                className="w-full rounded-2xl overflow-hidden mb-5 flex flex-col sm:flex-row transition-all hover:border-white/12"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
                <div className="sm:w-2/5 flex-shrink-0">
                    <img
                        src={featured.img_path}
                        alt={featured.title}
                        className="w-full h-48 sm:h-full object-cover"
                    />
                </div>
                <div className="flex flex-col justify-between p-7 flex-1">
                    <div>
                        <span
                            className="inline-block text-xs font-semibold px-2.5 py-1 rounded-full mb-3"
                            style={{ background: 'rgba(0,191,99,0.1)', color: 'var(--accent)' }}
                        >
                            Featured
                        </span>
                        <h2 className="text-2xl font-bold mb-3" style={{ color: 'var(--foreground)' }}>
                            {featured.title}
                        </h2>
                        <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                            {featured.info}
                        </p>
                    </div>
                    <Link
                        href={featured.redirect}
                        className="inline-flex items-center gap-1.5 mt-6 px-4 py-2 rounded-lg text-sm font-semibold text-white self-start transition-opacity hover:opacity-90"
                        style={{ background: 'linear-gradient(135deg, #00BF63, #00a854)' }}
                    >
                        Explore
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 10">
                            <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M1 5h12m0 0L9 1m4 4L9 9" />
                        </svg>
                    </Link>
                </div>
            </div>

            {/* Remaining cards — 2-column grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                {rest.map((item) => (
                    <div
                        key={item.id}
                        className="rounded-2xl overflow-hidden transition-all hover:border-white/12"
                        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
                    >
                        <img
                            src={item.img_path}
                            alt={item.title}
                            className="w-full h-44 object-cover"
                        />
                        <div className="p-6">
                            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--foreground)' }}>
                                {item.title}
                            </h3>
                            <p className="text-sm leading-relaxed mb-5" style={{ color: 'var(--muted)' }}>
                                {item.info}
                            </p>
                            <Link
                                href={item.redirect}
                                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white self-start transition-opacity hover:opacity-90"
                                style={{ background: 'linear-gradient(135deg, #00BF63, #00a854)' }}
                            >
                                Explore
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 10">
                                    <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M1 5h12m0 0L9 1m4 4L9 9" />
                                </svg>
                            </Link>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default About;

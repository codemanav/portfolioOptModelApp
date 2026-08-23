import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react'
import { Bars3Icon, XMarkIcon } from '@heroicons/react/24/outline'
import Link from "next/link";
import { usePathname } from 'next/navigation'

const navigation = [
  { name: 'Home', href: '/' },
  { name: 'Optimizer', href: '/prototype' },
  { name: 'About', href: '/about' },
]

export default function Navbar() {
  const pathname = usePathname();

  return (
    <Disclosure as="nav" className="glass fixed w-full z-50 border-b" style={{ borderColor: 'var(--border)' }}>
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="relative flex h-16 items-center justify-between">

          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 flex-shrink-0">
            <div
              className="w-7 h-7 rounded-md flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #00BF63, #38BDF8)' }}
            >
              <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="white" strokeWidth="2.5">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <span className="font-semibold text-sm tracking-tight" style={{ color: 'var(--foreground)' }}>
              EnergyOpt
            </span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden sm:flex items-center gap-1 absolute left-1/2 -translate-x-1/2">
            {navigation.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className="px-3.5 py-1.5 rounded-md text-sm font-medium transition-all hover:bg-white/5"
                  style={{ color: active ? 'var(--accent)' : 'var(--muted)' }}
                >
                  {item.name}
                </Link>
              );
            })}
          </div>

          {/* Mobile toggle */}
          <DisclosureButton
            className="group sm:hidden p-2 rounded-md hover:bg-white/5 transition-colors"
            style={{ color: 'var(--muted)' }}
          >
            <Bars3Icon className="h-5 w-5 group-data-[open]:hidden" />
            <XMarkIcon className="hidden h-5 w-5 group-data-[open]:block" />
          </DisclosureButton>
        </div>
      </div>

      {/* Mobile menu */}
      <DisclosurePanel className="sm:hidden border-t px-4 py-3 space-y-1" style={{ borderColor: 'var(--border)' }}>
        {navigation.map((item) => {
          const active = pathname === item.href;
          return (
            <DisclosureButton
              key={item.name}
              as="a"
              href={item.href}
              className="block px-3 py-2 rounded-md text-sm font-medium hover:bg-white/5 transition-all"
              style={{ color: active ? 'var(--accent)' : 'var(--muted)' }}
            >
              {item.name}
            </DisclosureButton>
          );
        })}
      </DisclosurePanel>
    </Disclosure>
  )
}

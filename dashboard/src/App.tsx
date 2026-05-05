import { BrowserRouter, NavLink, Routes, Route, useLocation } from 'react-router-dom'
import { LayoutDashboard, Zap, Eye, ListChecks, ScrollText, Users, Wifi, WifiOff } from 'lucide-react'
import { useWebSocket } from './api/useWebSocket'
import DashboardPage from './pages/DashboardPage'
import AccountsPage from './pages/AccountsPage'
import SeedingPage from './pages/SeedingPage'
import SpyPage from './pages/SpyPage'
import TasksPage from './pages/TasksPage'
import LogsPage from './pages/LogsPage'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', exact: true },
  { to: '/accounts', icon: Users, label: 'Accounts', exact: false },
  { to: '/tasks', icon: ListChecks, label: 'Tasks', exact: false },
  { to: '/seeding', icon: Zap, label: 'Seeding', exact: false },
  { to: '/spy', icon: Eye, label: 'Spy Ads', exact: false },
  { to: '/logs', icon: ScrollText, label: 'Logs', exact: false },
]

function PageTitle() {
  const loc = useLocation()
  const match = NAV.find(n => n.exact ? loc.pathname === n.to : loc.pathname.startsWith(n.to))
  return <span>{match?.label ?? 'Dashboard'}</span>
}

function Layout() {
  const { isConnected } = useWebSocket()

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
      {/* Left sidebar */}
      <aside className="w-48 flex-shrink-0 flex flex-col border-r" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="px-4 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--accent)' }}>
            FBKit
          </div>
          <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '2px' }}>Flow Agent</div>
        </div>
        <nav className="flex flex-col gap-1 px-2 py-3" style={{ flex: 1 }}>
          {NAV.map(({ to, icon: Icon, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded text-xs transition-colors ${
                  isActive ? 'font-semibold' : 'hover:opacity-80'
                }`
              }
              style={({ isActive }) => ({
                background: isActive ? 'var(--card)' : 'transparent',
                color: isActive ? 'var(--accent)' : 'var(--muted)',
              })}
            >
              <Icon size={14} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Connection status at bottom */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          {isConnected
            ? <Wifi size={11} color="var(--green)" />
            : <WifiOff size={11} color="var(--red)" />}
          <span style={{ fontSize: '10px', color: isConnected ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
            {isConnected ? 'Connected' : 'Offline'}
          </span>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Top header */}
        <header className="flex items-center justify-between px-5 py-3 border-b flex-shrink-0" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
            <PageTitle />
          </span>
          <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
            FBKit Agent v3
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-5">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/accounts" element={<AccountsPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/seeding" element={<SeedingPage />} />
            <Route path="/spy" element={<SpyPage />} />
            <Route path="/logs" element={<LogsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  )
}

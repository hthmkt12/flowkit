import type { CSSProperties, ReactNode } from 'react'
import { BrowserRouter, NavLink, Routes, Route, useLocation } from 'react-router-dom'
import {
  BarChart3,
  FileText,
  FlaskConical,
  Folder,
  Inbox,
  Layers,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Settings,
  Users,
  Zap,
} from 'lucide-react'
import DashboardPage from './pages/DashboardPage'
import AccountsPage from './pages/AccountsPage'
import SeedingPage from './pages/SeedingPage'
import TasksPage from './pages/TasksPage'
import LogsPage from './pages/LogsPage'
import AutoPostFanpagePage from './pages/AutoPostFanpagePage'
import AgentOnboardingPage from './pages/AgentOnboardingPage'
import ProjectsPage from './pages/ProjectsPage'
import CampaignsPage from './pages/CampaignsPage'

type DemoNavItem = {
  to: string
  icon: typeof LayoutDashboard
  label: string
  exact: boolean
  element: ReactNode
  future?: boolean
}

const NAV: DemoNavItem[] = [
  { to: '/', icon: LayoutDashboard, label: 'Demo Dashboard', exact: true, element: <DashboardPage /> },
  { to: '/settings', icon: Settings, label: 'Connect Agent', exact: false, element: <AgentOnboardingPage /> },
  { to: '/projects', icon: Folder, label: 'Autopilot Projects', exact: false, element: <ProjectsPage /> },
  { to: '/campaigns', icon: Layers, label: 'Campaign Planner', exact: false, element: <CampaignsPage /> },
  { to: '/posts', icon: FileText, label: 'Fanpage Dry Run', exact: false, element: <AutoPostFanpagePage /> },
  { to: '/accounts', icon: Users, label: 'Local Profiles', exact: false, element: <AccountsPage /> },
  { to: '/tasks', icon: FlaskConical, label: 'Local Tasks', exact: false, element: <TasksPage /> },
  { to: '/reports', icon: BarChart3, label: 'Evidence Log', exact: false, element: <LogsPage /> },
  { to: '/seeding', icon: Zap, label: 'Seeding (future)', exact: false, element: <SeedingPage />, future: true },
  { to: '/comments', icon: MessageCircle, label: 'Comments (future)', exact: false, element: <SeedingPage />, future: true },
  { to: '/inbox', icon: Inbox, label: 'Inbox (future)', exact: false, element: <TasksPage />, future: true },
]

function PageTitle() {
  const location = useLocation()
  const match = NAV.find(item => item.exact ? location.pathname === item.to : location.pathname.startsWith(item.to))
  return <span>{match?.label ?? 'Demo Dashboard'}</span>
}

function navItemStyle(isActive: boolean): CSSProperties {
  return {
    padding: '9px 10px',
    background: isActive ? 'rgba(255,255,255,0.14)' : 'transparent',
    color: isActive ? '#ffffff' : '#d8e7f8',
    fontSize: '12px',
    fontWeight: isActive ? 700 : 500,
  }
}

function futureItemStyle(): CSSProperties {
  return {
    padding: '9px 10px',
    color: '#9fb6d0',
    fontSize: '12px',
    fontWeight: 500,
    opacity: 0.68,
    cursor: 'not-allowed',
  }
}

function Layout() {
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
      <aside className="flex-shrink-0 flex flex-col" style={{ width: '200px', background: '#1e3a5f', color: '#eaf2ff' }}>
        <div style={{ padding: '18px 16px', borderBottom: '1px solid rgba(255,255,255,0.12)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '34px', height: '34px', borderRadius: '10px', background: '#3b82f6', display: 'grid', placeItems: 'center', fontWeight: 800 }}>Z</div>
            <div>
              <div style={{ fontSize: '17px', fontWeight: 800 }}>ZooPost</div>
              <div style={{ fontSize: '10px', color: '#bdd4ef' }}>Dry-run sales demo</div>
            </div>
          </div>
          <div style={{ marginTop: '14px', fontSize: '11px', lineHeight: 1.45, color: '#d8e7f8' }}>
            Phase 1 pilot: pair FBKit local, run fanpage dry-run, show safe progress evidence.
          </div>
        </div>

        <nav className="flex flex-col gap-1" style={{ flex: 1, padding: '12px 10px', overflowY: 'auto' }}>
          {NAV.map(({ to, icon: Icon, label, exact, future }) => (
            future ? (
              <div
                key={to}
                className="flex items-center gap-2 rounded"
                style={futureItemStyle()}
                title="Future module. Not part of the Phase 1 local pilot demo."
              >
                <Icon size={15} />
                <span style={{ lineHeight: 1.2 }}>{label}</span>
              </div>
            ) : (
              <NavLink
                key={to}
                to={to}
                end={exact}
                className="flex items-center gap-2 rounded transition-colors"
                style={({ isActive }) => navItemStyle(isActive)}
              >
                <Icon size={15} />
                <span style={{ lineHeight: 1.2 }}>{label}</span>
              </NavLink>
            )
          ))}
        </nav>

        <div style={{ padding: '12px 12px 16px', borderTop: '1px solid rgba(255,255,255,0.12)' }}>
          <button
            type="button"
            style={{
              width: '100%',
              border: 0,
              borderRadius: '9px',
              background: '#dc2626',
              color: '#fff',
              padding: '10px 12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              fontSize: '12px',
              fontWeight: 800,
            }}
          >
            <LogOut size={14} />
            Exit Demo
          </button>
        </div>
      </aside>

      <div className="flex flex-col flex-1 overflow-hidden">
        <header className="flex items-center justify-between px-5 py-3 border-b flex-shrink-0" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Sales demo / local pilot</div>
            <div className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
              <PageTitle />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', color: 'var(--muted)' }}>
            <span>Live actions disabled</span>
            <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: '#e2e8f0', color: '#1e3a5f', display: 'grid', placeItems: 'center', fontWeight: 800 }}>DR</div>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-5">
          <Routes>
            {NAV.filter(item => !item.future).map(item => <Route key={item.to} path={`${item.to}${item.to === '/' ? '' : '/*'}`} element={item.element} />)}
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

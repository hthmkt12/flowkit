import { BrowserRouter, NavLink, Routes, Route, useLocation } from 'react-router-dom'
import {
  BarChart3,
  CalendarDays,
  FileText,
  HelpCircle,
  Inbox,
  LayoutDashboard,
  Library,
  LogOut,
  MessageCircle,
  Settings,
  Users,
  Zap,
} from 'lucide-react'
import DashboardPage from './pages/DashboardPage'
import AccountsPage from './pages/AccountsPage'
import SeedingPage from './pages/SeedingPage'
import SpyPage from './pages/SpyPage'
import TasksPage from './pages/TasksPage'
import LogsPage from './pages/LogsPage'
import AutoPostFanpagePage from './pages/AutoPostFanpagePage'
import AgentOnboardingPage from './pages/AgentOnboardingPage'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Tổng Quan', exact: true, element: <DashboardPage /> },
  { to: '/calendar', icon: CalendarDays, label: 'Lịch đăng bài', exact: false, element: <TasksPage /> },
  { to: '/posts', icon: FileText, label: 'Bài viết', exact: false, element: <AutoPostFanpagePage /> },
  { to: '/accounts', icon: Users, label: 'Fanpage/Nhóm', exact: false, element: <AccountsPage /> },
  { to: '/library', icon: Library, label: 'Thư viện nội dung', exact: false, element: <TasksPage /> },
  { to: '/seeding', icon: Zap, label: 'Tự động seeding', exact: false, element: <SeedingPage /> },
  { to: '/comments', icon: MessageCircle, label: 'Bình luận tự động', exact: false, element: <SeedingPage /> },
  { to: '/inbox', icon: Inbox, label: 'Messenger/Inbox', exact: false, element: <TasksPage /> },
  { to: '/reports', icon: BarChart3, label: 'Báo cáo', exact: false, element: <LogsPage /> },
  { to: '/settings', icon: Settings, label: 'Cài đặt', exact: false, element: <AgentOnboardingPage /> },
  { to: '/guide', icon: HelpCircle, label: 'Hướng dẫn', exact: false, element: <LogsPage /> },
]

function PageTitle() {
  const location = useLocation()
  const match = NAV.find(item => item.exact ? location.pathname === item.to : location.pathname.startsWith(item.to))
  return <span>{match?.label ?? 'Tổng Quan'}</span>
}

function Layout() {
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
      <aside className="flex-shrink-0 flex flex-col" style={{ width: '200px', background: '#1e3a5f', color: '#eaf2ff' }}>
        <div style={{ padding: '18px 16px', borderBottom: '1px solid rgba(255,255,255,0.12)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '34px', height: '34px', borderRadius: '10px', background: '#3b82f6', display: 'grid', placeItems: 'center', fontWeight: 800 }}>Z</div>
            <div>
              <div style={{ fontSize: '17px', fontWeight: 800, letterSpacing: '-0.02em' }}>ZooPost</div>
              <div style={{ fontSize: '10px', color: '#bdd4ef' }}>SaaS Control Plane</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '14px' }}>
            <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: '#dbeafe', color: '#1e3a5f', display: 'grid', placeItems: 'center', fontSize: '12px', fontWeight: 700 }}>AD</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: '12px', fontWeight: 700 }}>Admin ZooPost</div>
              <div style={{ fontSize: '10px', color: '#bdd4ef' }}>Quản trị nội dung đa kênh</div>
            </div>
          </div>
        </div>

        <nav className="flex flex-col gap-1" style={{ flex: 1, padding: '12px 10px', overflowY: 'auto' }}>
          {NAV.map(({ to, icon: Icon, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className="flex items-center gap-2 rounded transition-colors"
              style={({ isActive }) => ({
                padding: '9px 10px',
                background: isActive ? 'rgba(255,255,255,0.14)' : 'transparent',
                color: isActive ? '#ffffff' : '#d8e7f8',
                fontSize: '12px',
                fontWeight: isActive ? 700 : 500,
              })}
            >
              <Icon size={15} />
              <span style={{ lineHeight: 1.2 }}>{label}</span>
            </NavLink>
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
            ĐĂNG XUẤT
          </button>
        </div>
      </aside>

      <div className="flex flex-col flex-1 overflow-hidden">
        <header className="flex items-center justify-between px-5 py-3 border-b flex-shrink-0" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Tổng Quan</div>
            <div className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
              <PageTitle />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', color: 'var(--muted)' }}>
            <span>ZooPost Cloud</span>
            <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: '#e2e8f0', color: '#1e3a5f', display: 'grid', placeItems: 'center', fontWeight: 800 }}>AD</div>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-5">
          <Routes>
            {NAV.map(item => <Route key={item.to} path={`${item.to}${item.to === '/' ? '' : '/*'}`} element={item.element} />)}
            <Route path="/tasks" element={<TasksPage />} />
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

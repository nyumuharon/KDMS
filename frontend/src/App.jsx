import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { Map as MapIcon, BarChart2, Users, Bell, FileText, Radar, Activity, HardHat } from 'lucide-react'
import MapView from './MapView'
import RiskPanel from './RiskPanel'
import WorkerPanel from './WorkerPanel'
import AlertConsole from './AlertConsole'
import AIReport from './AIReport'
import MotionBackground from './MotionBackground'
import './index.css'

const API = 'http://localhost:8000'

const NAV = [
  { path: '/', icon: MapIcon, label: 'Live Map' },
  { path: '/risk', icon: BarChart2, label: 'Risk Scores' },
  { path: '/workers', icon: Users, label: 'Workers' },
  { path: '/alerts', icon: Bell, label: 'Alert Console' },
  { path: '/report', icon: FileText, label: 'AI Report' },
]

function Sidebar({ stats }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon"><Radar size={20} color="white" /></div>
        <div>
          <div className="logo-text">KDMS</div>
          <div className="logo-sub">Kenya Disaster Mgmt</div>
        </div>
      </div>

      {NAV.map(n => {
        const Icon = n.icon
        return (
          <NavLink
            key={n.path}
            to={n.path}
            end={n.path === '/'}
            className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
          >
            <span className="nav-icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon size={18} />
            </span>
            {n.label}
          </NavLink>
        )
      })}

      <div className="sidebar-bottom">
        <div className="sync-badge">
          <div className="sync-dot" />
          Live monitoring active
        </div>
        {stats && (
          <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-muted)' }}>
            {stats.counties_monitored} counties · {stats.available_workers} workers ready
          </div>
        )}
      </div>
    </aside>
  )
}

function Topbar({ stats }) {
  const loc = useLocation()
  const titles = {
    '/': 'Live Disaster Map',
    '/risk': 'County Risk Scores',
    '/workers': 'Field Workers',
    '/alerts': 'Alert Console',
    '/report': 'AI Situation Report',
  }
  return (
    <header className="topbar">
      <h1>{titles[loc.pathname] || 'KDMS'}</h1>
      {stats && (
        <>
          <div className="stat-pill red">
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Activity size={14} /> Active</span>
            <span className="val">{stats.active_disasters}</span>
          </div>
          <div className="stat-pill amber">
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Users size={14} /> Affected</span>
            <span className="val">{(stats.total_affected || 0).toLocaleString()}</span>
          </div>
          <div className="stat-pill green">
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><HardHat size={14} /> Deployed</span>
            <span className="val">{stats.deployed_workers}</span>
          </div>
        </>
      )}
    </header>
  )
}

export default function App() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    const load = () =>
      fetch(`${API}/stats`)
        .then(r => r.json())
        .then(setStats)
        .catch(() => { })
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])

  return (
    <BrowserRouter>
      <div className="app-shell">
        <MotionBackground />
        <Sidebar stats={stats} />
        <div className="main-content">
          <Topbar stats={stats} />
          <main className="page">
            <Routes>
              <Route path="/" element={<MapView api={API} />} />
              <Route path="/risk" element={<RiskPanel api={API} />} />
              <Route path="/workers" element={<WorkerPanel api={API} />} />
              <Route path="/alerts" element={<AlertConsole api={API} />} />
              <Route path="/report" element={<AIReport api={API} />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}

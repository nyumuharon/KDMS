import React, { useState, useEffect } from 'react'
import { Stethoscope, Search, Cross, Radio, Package, UserX, Send, CheckCircle2 } from 'lucide-react'

const STATUS_STYLE = {
    available: { color: 'var(--accent-green)', bg: 'rgba(16,185,129,0.1)', label: 'Available' },
    deployed: { color: 'var(--accent-amber)', bg: 'rgba(245,158,11,0.1)', label: 'Deployed' },
    offline: { color: 'var(--text-muted)', bg: 'rgba(100,116,139,0.1)', label: 'Offline' },
}

const ROLE_ICON = {
    'Paramedic': <Stethoscope size={16} />,
    'Search & Rescue': <Search size={16} />,
    'Medical Officer': <Cross size={16} />,
    'Field Coordinator': <Radio size={16} />,
    'Logistics': <Package size={16} />,
}

export default function WorkerPanel({ api }) {
    const [workers, setWorkers] = useState([])
    const [disasters, setDisasters] = useState([])
    const [loading, setLoading] = useState(true)
    const [modal, setModal] = useState(null)   // worker being dispatched
    const [dispDisId, setDispDisId] = useState('')
    const [toast, setToast] = useState(null)
    const [filter, setFilter] = useState('')

    const load = () => {
        Promise.all([
            fetch(`${api}/workers`).then(r => r.json()),
            fetch(`${api}/disasters?status=active`).then(r => r.json()),
        ]).then(([w, d]) => {
            setWorkers(w)
            setDisasters(d)
            setLoading(false)
        }).catch(() => setLoading(false))
    }

    useEffect(() => { load() }, [api])

    const showToast = (msg, type = 'success') => {
        setToast({ msg, type })
        setTimeout(() => setToast(null), 3500)
    }

    const dispatch = async () => {
        if (!dispDisId) return
        try {
            const res = await fetch(`${api}/dispatch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ worker_id: modal.id, disaster_id: parseInt(dispDisId) }),
            })
            const data = await res.json()
            showToast(`✅ ${data.message}`)
            setModal(null)
            setDispDisId('')
            load()
        } catch {
            showToast('❌ Dispatch failed', 'error')
        }
    }

    const filtered = workers.filter(w =>
        w.name.toLowerCase().includes(filter.toLowerCase()) ||
        (w.role || '').toLowerCase().includes(filter.toLowerCase())
    )

    const deployed = workers.filter(w => w.status === 'deployed').length
    const available = workers.filter(w => w.status === 'available').length

    if (loading) return (
        <div className="loading-center"><div className="spinner" /><span>Loading workers…</span></div>
    )

    return (
        <div>
            {/* Summary */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center' }}>
                <div className="card" style={{ padding: '10px 18px', display: 'flex', gap: 10, alignItems: 'center' }}>
                    <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--accent-green)' }}>{available}</span>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Available</span>
                </div>
                <div className="card" style={{ padding: '10px 18px', display: 'flex', gap: 10, alignItems: 'center' }}>
                    <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--accent-amber)' }}>{deployed}</span>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Deployed</span>
                </div>
                <div style={{ marginLeft: 'auto' }}>
                    <input
                        className="form-control"
                        placeholder="🔍 Search workers…"
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                        style={{ width: 200, padding: '8px 12px' }}
                    />
                </div>
            </div>

            {/* Table */}
            <div className="card">
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Worker</th>
                            <th>Role</th>
                            <th>County</th>
                            <th>Phone</th>
                            <th>Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.map(w => {
                            const st = STATUS_STYLE[w.status] || STATUS_STYLE.offline
                            return (
                                <tr>
                                    <td>
                                        <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <span style={{ color: 'var(--text-muted)' }}>{ROLE_ICON[w.role] || <UserX size={16} />}</span>
                                            {w.name}
                                        </div>
                                    </td>
                                    <td style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{w.role}</td>
                                    <td style={{ color: 'var(--text-secondary)' }}>{w.county_name || '—'}</td>
                                    <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: 'var(--text-muted)' }}>
                                        {w.phone}
                                    </td>
                                    <td>
                                        <span style={{
                                            display: 'inline-block',
                                            padding: '3px 10px', borderRadius: 20,
                                            fontSize: 11, fontWeight: 700,
                                            background: st.bg, color: st.color,
                                        }}>
                                            {st.label}
                                        </span>
                                    </td>
                                    <td>
                                        <button
                                            className="btn btn-primary btn-sm"
                                            disabled={w.status === 'deployed' || disasters.length === 0}
                                            onClick={() => { setModal(w); setDispDisId('') }}
                                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                                        >
                                            {w.status === 'deployed' ? <><CheckCircle2 size={14} /> Deployed</> : <><Send size={14} /> Dispatch</>}
                                        </button>
                                    </td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
                {filtered.length === 0 && (
                    <div className="empty-state">
                        <div className="icon" style={{ marginBottom: 16 }}><UserX size={48} color="rgba(255,255,255,0.1)" /></div>
                        <p>No workers match your search</p>
                    </div>
                )}
            </div>

            {/* Dispatch modal */}
            {
                modal && (
                    <div style={{
                        position: 'fixed', inset: 0,
                        background: 'rgba(0,0,0,0.6)',
                        backdropFilter: 'blur(4px)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        zIndex: 9000,
                    }}>
                        <div className="card" style={{ width: 420, padding: 28 }}>
                            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Send size={18} color="var(--accent-primary)" /> Dispatch {modal.name}
                            </div>
                            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
                                {modal.role} · {modal.county_name}
                            </div>

                            <div className="form-group">
                                <label>Select Disaster</label>
                                <select
                                    className="form-control"
                                    value={dispDisId}
                                    onChange={e => setDispDisId(e.target.value)}
                                >
                                    <option value="">— Choose disaster —</option>
                                    {disasters.map(d => (
                                        <option key={d.id} value={d.id}>
                                            {d.type} — {d.location} ({d.severity})
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                                <button className="btn btn-primary" style={{ flex: 1 }} onClick={dispatch} disabled={!dispDisId}>
                                    Confirm Dispatch
                                </button>
                                <button className="btn btn-danger" onClick={() => setModal(null)}>
                                    Cancel
                                </button>
                            </div>
                        </div>
                    </div>
                )
            }

            {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
        </div >
    )
}

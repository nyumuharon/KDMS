import React, { useState, useEffect, useRef } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const SEVERITY_COLOR = {
    High: '#ef4444',
    Medium: '#f59e0b',
    Low: '#10b981',
}

const TYPE_ICON = {
    Flood: '🌊',
    Wildfire: '🔥',
    Drought: '☀️',
    Earthquake: '🌎',
    Landslide: '⛰️',
    default: '⚠️',
}

function FitBounds({ disasters }) {
    const map = useMap()
    useEffect(() => {
        if (disasters.length) {
            const lats = disasters.map(d => d.lat).filter(Boolean)
            const lngs = disasters.map(d => d.lng).filter(Boolean)
            if (lats.length && lngs.length) {
                map.fitBounds(
                    [[Math.min(...lats) - 0.5, Math.min(...lngs) - 0.5],
                    [Math.max(...lats) + 0.5, Math.max(...lngs) + 0.5]],
                    { maxZoom: 9 }
                )
            }
        }
    }, [disasters])
    return null
}

export default function MapView({ api }) {
    const [disasters, setDisasters] = useState([])
    const [selected, setSelected] = useState(null)
    const [loading, setLoading] = useState(true)
    const [toast, setToast] = useState(null)

    useEffect(() => {
        fetch(`${api}/disasters?status=active`)
            .then(r => r.json())
            .then(data => { setDisasters(data); setLoading(false) })
            .catch(() => setLoading(false))
        const t = setInterval(() =>
            fetch(`${api}/disasters?status=active`)
                .then(r => r.json())
                .then(setDisasters)
                .catch(() => { }), 60000)
        return () => clearInterval(t)
    }, [api])

    const showToast = (msg, type = 'success') => {
        setToast({ msg, type })
        setTimeout(() => setToast(null), 3000)
    }

    const resolve = async (id) => {
        await fetch(`${api}/disasters/${id}/resolve`, { method: 'PATCH' })
        setDisasters(prev => prev.filter(d => d.id !== id))
        showToast('✅ Disaster marked as resolved')
    }

    return (
        <div style={{ position: 'relative' }}>
            {/* Legend */}
            <div style={{
                display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center'
            }}>
                {['High', 'Medium', 'Low'].map(s => (
                    <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                        <div style={{
                            width: 12, height: 12, borderRadius: '50%',
                            background: SEVERITY_COLOR[s], boxShadow: `0 0 6px ${SEVERITY_COLOR[s]}`
                        }} />
                        <span style={{ color: 'var(--text-secondary)' }}>{s} Severity</span>
                    </div>
                ))}
                <div style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>
                    {loading ? '⏳ Loading...' : `${disasters.length} active disaster${disasters.length !== 1 ? 's' : ''}`}
                </div>
            </div>

            <div className="map-container">
                <MapContainer
                    center={[0.2, 37.9]}
                    zoom={6}
                    style={{ height: '100%', width: '100%' }}
                >
                    <TileLayer
                        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                    />
                    {disasters.filter(d => d.lat && d.lng).map(d => (
                        <CircleMarker
                            key={d.id}
                            center={[d.lat, d.lng]}
                            radius={d.severity === 'High' ? 14 : d.severity === 'Medium' ? 10 : 7}
                            pathOptions={{
                                color: SEVERITY_COLOR[d.severity] || '#f59e0b',
                                fillColor: SEVERITY_COLOR[d.severity] || '#f59e0b',
                                fillOpacity: 0.75,
                                weight: 2,
                            }}
                            eventHandlers={{ click: () => setSelected(d) }}
                        >
                            <Popup className="kdms-popup">
                                <div style={{
                                    background: '#0a1628',
                                    border: '1px solid rgba(99,158,255,0.2)',
                                    borderRadius: 10,
                                    padding: '14px 16px',
                                    minWidth: 220,
                                    color: '#f0f4ff',
                                    fontFamily: 'Inter, sans-serif',
                                }}>
                                    <div style={{ fontSize: 20, marginBottom: 6 }}>
                                        {TYPE_ICON[d.type] || TYPE_ICON.default} {d.type}
                                    </div>
                                    <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>{d.location}</div>
                                    <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 8 }}>
                                        {d.county_name && <span>📍 {d.county_name} · </span>}
                                        <span style={{ color: SEVERITY_COLOR[d.severity] }}>⚠ {d.severity}</span>
                                    </div>
                                    {d.affected_people > 0 && (
                                        <div style={{ fontSize: 13, marginBottom: 6, color: '#CBD5E1' }}>
                                            👥 {d.affected_people.toLocaleString()} affected
                                        </div>
                                    )}
                                    {d.description && (
                                        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 10, lineHeight: 1.5 }}>
                                            {d.description}
                                        </div>
                                    )}
                                    <button
                                        onClick={() => resolve(d.id)}
                                        style={{
                                            width: '100%', padding: '7px 12px',
                                            background: 'rgba(16,185,129,0.15)',
                                            border: '1px solid rgba(16,185,129,0.35)',
                                            borderRadius: 7, color: '#10b981',
                                            fontSize: 12, fontWeight: 600,
                                            cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                                        }}
                                    >
                                        ✓ Mark Resolved
                                    </button>
                                </div>
                            </Popup>
                        </CircleMarker>
                    ))}

                    <FitBounds disasters={disasters} />
                </MapContainer>
            </div>

            {
                toast && (
                    <div className={`toast ${toast.type}`}>{toast.msg}</div>
                )
            }
        </div >
    )
}

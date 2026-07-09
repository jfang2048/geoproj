import { useEffect, useMemo, useState } from 'react'
import { GeoJSON, MapContainer, TileLayer, useMap } from 'react-leaflet'
import { api, apiUrl } from '../api/client.js'

function FitLayers({ layers }) {
  const map = useMap()
  useEffect(() => {
    const bounds = []
    layers.forEach((layer) => {
      try {
        const coords = collectCoords(layer.data)
        coords.forEach(([lng, lat]) => bounds.push([lat, lng]))
      } catch (_) {}
    })
    if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] })
  }, [layers, map])
  return null
}

function collectCoords(geojson) {
  const coords = []
  function walk(value) {
    if (!value) return
    if (typeof value[0] === 'number' && typeof value[1] === 'number') coords.push(value)
    else if (Array.isArray(value)) value.forEach(walk)
  }
  ;(geojson.features || []).forEach((feature) => walk(feature.geometry?.coordinates))
  return coords
}

function styleFor(layerId) {
  if (layerId.includes('runoff_delta')) return { color: '#b91c1c', weight: 1, fillColor: '#f97316', fillOpacity: 0.55 }
  if (layerId.includes('response_units')) return { color: '#6d28d9', weight: 1, fillOpacity: 0.18 }
  if (layerId.includes('catchment')) return { color: '#111827', weight: 3, fillOpacity: 0.02 }
  if (layerId.includes('fire')) return { color: '#dc2626', weight: 2, fillOpacity: 0.12 }
  if (layerId.includes('burn')) return { color: '#ea580c', weight: 1, fillOpacity: 0.35 }
  if (layerId.includes('land')) return { color: '#15803d', weight: 1, fillOpacity: 0.25 }
  return { color: '#2563eb', weight: 1, fillOpacity: 0.2 }
}

export default function MapViewer({ runId, refreshToken }) {
  const [catalog, setCatalog] = useState([])
  const [visible, setVisible] = useState({})
  const [loadedLayers, setLoadedLayers] = useState([])
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!runId) return
    api.listLayers(runId).then((layers) => {
      setCatalog(layers)
      const nextVisible = {}
      layers.filter((layer) => layer.exists).forEach((layer) => { nextVisible[layer.layer_id] = true })
      setVisible(nextVisible)
    }).catch((err) => setMessage(err.message))
  }, [runId, refreshToken])

  useEffect(() => {
    async function load() {
      const layers = []
      for (const item of catalog.filter((layer) => layer.exists && visible[layer.layer_id])) {
        try {
          const data = await fetch(apiUrl(item.url)).then((response) => response.json())
          layers.push({ ...item, data })
        } catch (err) {
          setMessage(`Could not load ${item.label}: ${err.message}`)
        }
      }
      setLoadedLayers(layers)
    }
    load()
  }, [catalog, visible])

  const missing = useMemo(() => catalog.filter((layer) => !layer.exists), [catalog])
  const existing = useMemo(() => catalog.filter((layer) => layer.exists), [catalog])

  return (
    <section className="panel map-panel">
      <div className="panel-header-row">
        <h2>Map viewer</h2>
        {message && <span className="status-text">{message}</span>}
      </div>
      <div className="map-layout">
        <MapContainer center={[45.86, 8.78]} zoom={11} className="map-container">
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {loadedLayers.map((layer) => <GeoJSON
            key={layer.layer_id}
            data={layer.data}
            style={() => styleFor(layer.layer_id)}
            onEachFeature={(feature, leafletLayer) => {
              const props = feature.properties || {}
              const html = Object.entries(props).slice(0, 12).map(([k, v]) => `<b>${k}</b>: ${v}`).join('<br/>')
              leafletLayer.bindPopup(html || layer.label)
            }}
          />)}
          <FitLayers layers={loadedLayers} />
        </MapContainer>
        <aside className="layer-sidebar">
          <h3>Layers</h3>
          {existing.length === 0 && <p>No output for this run yet.<br />Run preprocessing and model calculation first.</p>}
          {existing.map((layer) => <label key={layer.layer_id} className="checkbox-row">
            <input type="checkbox" checked={!!visible[layer.layer_id]} onChange={(e) => setVisible({ ...visible, [layer.layer_id]: e.target.checked })} />
            {layer.label}
          </label>)}
          <h3>Legend</h3>
          <ul className="legend-list">
            {existing.map((layer) => <li key={`legend-${layer.layer_id}`}>
              <span className="legend-swatch" style={{ backgroundColor: styleFor(layer.layer_id).fillColor || styleFor(layer.layer_id).color, borderColor: styleFor(layer.layer_id).color }} />
              {layer.label}
            </li>)}
          </ul>
          <h3>Missing layers</h3>
          <ul className="missing-list">
            {missing.map((layer) => <li key={layer.layer_id}><strong>{layer.label}</strong>: {layer.reason}</li>)}
          </ul>
        </aside>
      </div>
    </section>
  )
}

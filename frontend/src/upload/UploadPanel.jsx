import { useState } from 'react'
import { api } from '../api/client.js'

const CATEGORIES = [
  ['dem', 'DEM raster', '.tif,.tiff'],
  ['fire_perimeter', 'Burned area or fire perimeter vector', '.gpkg,.geojson,.zip'],
  ['burn_severity', 'Burn severity raster or vector', '.tif,.tiff,.gpkg,.geojson,.zip'],
  ['land_cover', 'Land cover raster or vector', '.tif,.tiff,.gpkg,.geojson,.zip'],
  ['hydrologic_soil_group', 'Hydrologic soil group raster or vector', '.tif,.tiff,.gpkg,.geojson,.zip'],
  ['rainfall', 'Rainfall event CSV', '.csv'],
  ['water_body', 'Lake or water body vector', '.gpkg,.geojson,.zip'],
  ['hydrography', 'Hydrography vector', '.gpkg,.geojson,.zip']
]

export default function UploadPanel({ runId, onChanged }) {
  const [category, setCategory] = useState('dem')
  const [file, setFile] = useState(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const current = CATEGORIES.find(([id]) => id === category)

  async function upload() {
    if (!runId) return setMessage('Create or select a run first.')
    if (!file) return setMessage('Choose a file to upload.')
    setBusy(true)
    setMessage('Validating upload...')
    try {
      const result = await api.upload(runId, category, file)
      setMessage(`Accepted ${result.filename}`)
      setFile(null)
      onChanged?.()
    } catch (err) {
      setMessage(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel">
      <h2>Upload data</h2>
      <label>
        Data category
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
      </label>
      <label>
        Select file
        <input type="file" accept={current?.[2]} onChange={(e) => setFile(e.target.files?.[0] || null)} />
      </label>
      <button disabled={busy || !runId} onClick={upload}>Upload and validate</button>
      {message && <p className="status-text">{message}</p>}
    </section>
  )
}

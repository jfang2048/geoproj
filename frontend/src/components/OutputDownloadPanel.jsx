import { useEffect, useState } from 'react'
import { api, apiUrl } from '../api/client.js'

export default function OutputDownloadPanel({ runId, refreshToken }) {
  const [items, setItems] = useState([])
  const [message, setMessage] = useState('')
  useEffect(() => {
    if (!runId) return
    api.listDownloads(runId).then(setItems).catch((err) => setMessage(err.message))
  }, [runId, refreshToken])
  return (
    <section className="panel">
      <h2>Download outputs</h2>
      {message && <p className="status-text">{message}</p>}
      {items.length === 0 && <p>No output for this run yet. Run preprocessing and model calculation first.</p>}
      <ul className="download-list">
        {items.map((item) => <li key={`${item.key}-${item.path}`}>
          <a href={apiUrl(item.url)} download>{item.key}</a>
          <span>{item.description}</span>
          <code>{item.checksum_sha256.slice(0, 12)}</code>
        </li>)}
      </ul>
    </section>
  )
}

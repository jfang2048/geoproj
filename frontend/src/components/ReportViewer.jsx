import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

export default function ReportViewer({ runId, refreshToken }) {
  const [report, setReport] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    async function load() {
      if (!runId) return
      try {
        const downloads = await api.listDownloads(runId)
        const item = downloads.find((entry) => entry.key === 'run_report')
        if (!item) {
          setReport('')
          setMessage('No report for this run yet. Run model calculation or write QA report first.')
          return
        }
        const text = await api.text(item.url)
        setReport(text)
        setMessage('')
      } catch (err) {
        setMessage(err.message)
      }
    }
    load()
  }, [runId, refreshToken])

  return (
    <section className="panel report-panel">
      <h2>Run report</h2>
      {message && <p className="status-text">{message}</p>}
      {report && <pre>{report}</pre>}
    </section>
  )
}

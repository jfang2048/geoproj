import { useEffect, useState } from 'react'
import { api } from './api/client.js'
import RunPage from './pages/RunPage.jsx'

export default function App() {
  const [runs, setRuns] = useState([])
  const [selectedRunId, setSelectedRunId] = useState('')
  const [error, setError] = useState('')

  async function refreshRuns(nextRunId) {
    try {
      const data = await api.listRuns()
      setRuns(data)
      if (nextRunId) setSelectedRunId(nextRunId)
      else if (!selectedRunId && data.length) setSelectedRunId(data[0].run_id)
    } catch (err) {
      setError(err.message)
    }
  }

  async function createRun(name) {
    try {
      const manifest = await api.createRun(name)
      await refreshRuns(manifest.run_id)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { refreshRuns() }, [])

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>Post-fire runoff screening</h1>
          <p>Upload GIS and rainfall data, validate inputs, run screening calculations, and inspect outputs.</p>
        </div>
      </header>
      {error && <div className="error-banner">{error}</div>}
      <RunPage
        runs={runs}
        selectedRunId={selectedRunId}
        onSelectRun={setSelectedRunId}
        onCreateRun={createRun}
        onRefreshRuns={refreshRuns}
      />
    </main>
  )
}

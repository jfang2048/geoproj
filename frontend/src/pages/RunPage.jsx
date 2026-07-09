import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client.js'
import RunSelector from '../components/RunSelector.jsx'
import UploadPanel from '../upload/UploadPanel.jsx'
import ValidationStatusPanel from '../components/ValidationStatusPanel.jsx'
import ProcessingPanel from '../components/ProcessingPanel.jsx'
import MapViewer from '../map/MapViewer.jsx'
import OutputDownloadPanel from '../components/OutputDownloadPanel.jsx'
import ReportViewer from '../components/ReportViewer.jsx'

export default function RunPage({ runs, selectedRunId, onSelectRun, onCreateRun, onRefreshRuns }) {
  const [manifest, setManifest] = useState(null)
  const [refreshToken, setRefreshToken] = useState(0)

  const refresh = useCallback(async () => {
    if (!selectedRunId) return setManifest(null)
    const data = await api.getRun(selectedRunId)
    setManifest(data)
    setRefreshToken((value) => value + 1)
    onRefreshRuns?.(selectedRunId)
  }, [selectedRunId])

  useEffect(() => { refresh().catch(() => {}) }, [refresh])

  return (
    <div className="workspace-grid">
      <div className="left-column">
        <RunSelector runs={runs} selectedRunId={selectedRunId} onSelectRun={onSelectRun} onCreateRun={onCreateRun} />
        <UploadPanel runId={selectedRunId} onChanged={refresh} />
        <ValidationStatusPanel manifest={manifest} />
        <ProcessingPanel runId={selectedRunId} onChanged={refresh} />
        <OutputDownloadPanel runId={selectedRunId} refreshToken={refreshToken} />
      </div>
      <div className="right-column">
        <MapViewer runId={selectedRunId} refreshToken={refreshToken} />
        <ReportViewer runId={selectedRunId} refreshToken={refreshToken} />
      </div>
    </div>
  )
}

import { useState } from 'react'

export default function RunSelector({ runs, selectedRunId, onSelectRun, onCreateRun }) {
  const [name, setName] = useState('')
  return (
    <section className="panel">
      <h2>Project/run</h2>
      <label>
        Select run
        <select value={selectedRunId || ''} onChange={(e) => onSelectRun(e.target.value)}>
          <option value="">No run selected</option>
          {runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.name} · {run.status}</option>)}
        </select>
      </label>
      <div className="inline-form">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Run name" />
        <button onClick={() => { onCreateRun(name || undefined); setName('') }}>Create run</button>
      </div>
    </section>
  )
}

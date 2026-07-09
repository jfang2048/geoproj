import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

export default function ProcessingPanel({ runId, onChanged }) {
  const [job, setJob] = useState(null)
  const [message, setMessage] = useState('')
  const [hsgFallback, setHsgFallback] = useState('')

  async function start(step) {
    if (!runId) return setMessage('Create or select a run first.')
    const parameters = {}
    if (step === 'modeling' && hsgFallback) parameters.hsg_fallback = hsgFallback
    try {
      const started = await api.startJob(runId, step, parameters)
      setJob(started)
      setMessage(started.progress_message)
    } catch (err) {
      setMessage(err.message)
    }
  }

  useEffect(() => {
    if (!runId || !job || ['succeeded', 'failed'].includes(job.status)) return
    const timer = setInterval(async () => {
      try {
        const next = await api.getJob(runId, job.job_id)
        setJob(next)
        setMessage(next.error_message || next.progress_message)
        if (['succeeded', 'failed'].includes(next.status)) onChanged?.()
      } catch (err) {
        setMessage(err.message)
      }
    }, 1500)
    return () => clearInterval(timer)
  }, [runId, job, onChanged])

  return (
    <section className="panel">
      <h2>Processing</h2>
      <div className="button-row">
        <button disabled={!runId} onClick={() => start('preprocessing')}>Run preprocessing</button>
        <button disabled={!runId} onClick={() => start('modeling')}>Run runoff model</button>
        <button disabled={!runId} onClick={() => start('qa_report')}>Write QA report</button>
      </div>
      <label>
        HSG fallback for this run only
        <select value={hsgFallback} onChange={(e) => setHsgFallback(e.target.value)}>
          <option value="">No fallback; require HSG upload</option>
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="C">C</option>
          <option value="D">D</option>
        </select>
      </label>
      {message && <p className="status-text">{message}</p>}
      {job && <dl className="job-status">
        <dt>Job ID</dt><dd>{job.job_id}</dd>
        <dt>Status</dt><dd>{job.status}</dd>
        <dt>Log file</dt><dd>{job.log_file_path}</dd>
      </dl>}
    </section>
  )
}

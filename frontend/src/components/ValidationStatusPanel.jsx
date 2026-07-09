const REQUIRED = ['dem', 'fire_perimeter', 'burn_severity', 'land_cover', 'rainfall', 'hydrologic_soil_group']

export default function ValidationStatusPanel({ manifest }) {
  const inputs = manifest?.inputs || {}
  return (
    <section className="panel">
      <h2>Validation status</h2>
      {!manifest && <p>Select a run to view validation status.</p>}
      {manifest && <>
        <table className="compact-table">
          <thead><tr><th>Input</th><th>Status</th><th>CRS</th><th>Notes</th></tr></thead>
          <tbody>
            {REQUIRED.map((category) => {
              const entry = inputs[category]
              const metadata = entry?.metadata || {}
              return <tr key={category}>
                <td>{category}</td>
                <td>{entry ? 'Accepted' : 'Missing required file'}</td>
                <td>{metadata.crs || (category === 'rainfall' ? 'table' : '')}</td>
                <td>{(metadata.warnings || []).join('; ')}</td>
              </tr>
            })}
          </tbody>
        </table>
        {(manifest.warnings || []).length > 0 && <div className="warning-box">
          <strong>Warnings</strong>
          <ul>{manifest.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>}
        {(manifest.fatal_errors || []).length > 0 && <div className="error-box">
          <strong>Fatal errors</strong>
          <ul>{manifest.fatal_errors.map((e, i) => <li key={i}>{e.message || e}</li>)}</ul>
        </div>}
      </>}
    </section>
  )
}

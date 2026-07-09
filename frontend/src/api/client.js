const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      message = body.message || message
    } catch (_) {}
    throw new Error(message)
  }
  const type = response.headers.get('content-type') || ''
  if (type.includes('application/json')) return response.json()
  return response.text()
}

export const api = {
  listRuns: () => request('/api/runs'),
  createRun: (name) => request('/api/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  }),
  getRun: (runId) => request(`/api/runs/${runId}`),
  upload: (runId, category, file) => {
    const form = new FormData()
    form.append('file', file)
    return request(`/api/runs/${runId}/uploads/${category}`, { method: 'POST', body: form })
  },
  startJob: (runId, step, parameters = {}) => request(`/api/runs/${runId}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ step, parameters })
  }),
  getJob: (runId, jobId) => request(`/api/runs/${runId}/jobs/${jobId}`),
  listLayers: (runId) => request(`/api/runs/${runId}/layers`),
  listDownloads: (runId) => request(`/api/runs/${runId}/downloads`),
  text: (url) => request(url)
}

export function apiUrl(path) {
  return `${API_BASE}${path}`
}

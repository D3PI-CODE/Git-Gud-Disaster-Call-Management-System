import { useState, useRef, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const STEPS = [
  { key: 'transcribe', label: 'Transcribing via VALSEA'       },
  { key: 'sentiment',  label: 'Analysing sentiment'            },
  { key: 'prosody',    label: 'Detecting urgency & stress'     },
  { key: 'gemini',     label: 'Extracting key notes (Gemini)'  },
  { key: 'saving',     label: 'Saving to ResQNet'              },
]

function useTimer(running) {
  const [s, setS] = useState(0)
  useEffect(() => {
    if (!running) { setS(0); return }
    const id = setInterval(() => setS(n => n + 1), 1000)
    return () => clearInterval(id)
  }, [running])
  return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`
}

export default function AudioRecorder() {
  const [name,     setName]     = useState('')
  const [location, setLocation] = useState('')
  const [status,   setStatus]   = useState('idle')
  const [blob,     setBlob]     = useState(null)
  const [stepIdx,  setStepIdx]  = useState(0)
  const [errMsg,   setErrMsg]   = useState('')
  const [priority, setPriority] = useState(null)

  const mrRef     = useRef(null)
  const chunksRef = useRef([])
  const timer     = useTimer(status === 'recording')

  async function startRec() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = () => { setBlob(new Blob(chunksRef.current, { type: 'audio/webm' })); stream.getTracks().forEach(t => t.stop()) }
      mr.start(250); mrRef.current = mr; setStatus('recording')
    } catch { setErrMsg('Microphone access denied.') }
  }

  function stopRec() { mrRef.current?.stop(); setStatus('idle') }

  async function submit() {
    if (!blob) return
    setStatus('processing'); setStepIdx(0); setErrMsg('')
    let i = 0
    const t = setInterval(() => { i++; if (i < STEPS.length) setStepIdx(i); else clearInterval(t) }, 2600)
    try {
      const form = new FormData()
      form.append('audio',          new File([blob], 'incident.webm', { type: 'audio/webm' }))
      form.append('caller_name',    name     || 'Agent Submission')
      form.append('contact_number', '')
      form.append('incident_type',  'disaster')
      const res  = await fetch(`${API_URL}/incident`, { method: 'POST', body: form })
      clearInterval(t)
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Server error ${res.status}`) }
      const data = await res.json()
      setPriority(data.priority); setStatus('success')
    } catch (e) { clearInterval(t); setErrMsg(e.message || 'Something went wrong.'); setStatus('error') }
  }

  function reset() { setStatus('idle'); setBlob(null); setName(''); setLocation(''); setStepIdx(0); setErrMsg(''); setPriority(null) }

  const PCOLORS = { critical: 'var(--p-critical)', high: 'var(--p-high)', medium: 'var(--p-medium)', low: 'var(--p-low)' }

  if (status === 'success') return (
    <>
      <div className="section-label"><span className="sl-text">New Incident</span><span className="sl-line"/></div>
      <div className="success-card">
        <div style={{ fontSize: 34 }}>✅</div>
        <div className="success-title">Incident Logged</div>
        {priority && (
          <div className="p-badge" style={{ background: `${PCOLORS[priority]}18`, border: `1px solid ${PCOLORS[priority]}44`, color: PCOLORS[priority], fontSize: 10, padding: '5px 14px' }}>
            ● {priority?.toUpperCase()} PRIORITY
          </div>
        )}
        <div className="success-sub">Now visible on the live feed.</div>
        <button className="reset-btn" onClick={reset}>+ Log Another</button>
      </div>
    </>
  )

  return (
    <>
      <div className="section-label"><span className="sl-text">New Incident</span><span className="sl-line"/></div>
      <div className="incident-form">
        <div className="form-row">
          <label className="form-label">Caller Name</label>
          <input className="form-input" placeholder="e.g. Priya Nair" value={name} onChange={e => setName(e.target.value)} disabled={status === 'processing'}/>
        </div>
        <div className="form-row">
          <label className="form-label">Location</label>
          <input className="form-input" placeholder="e.g. Batticaloa, Eastern Province" value={location} onChange={e => setLocation(e.target.value)} disabled={status === 'processing'}/>
        </div>

        <div className="record-zone">
          <div className="waveform">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className={`wv-bar ${status === 'recording' ? 'active' : ''}`}/>
            ))}
          </div>
          <div className={`rec-btn-wrap ${status === 'recording' ? 'recording' : ''}`}>
            <div className="rec-ring"/>
            <button className={`rec-btn ${status === 'recording' ? 'recording' : ''}`} onClick={status === 'recording' ? stopRec : startRec} disabled={status === 'processing'}>
              {status === 'recording' ? (
                <svg width="20" height="20" viewBox="0 0 20 20" fill="var(--p-critical)"><rect x="3" y="3" width="14" height="14" rx="3"/></svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--txt-secondary)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4z"/>
                  <path d="M19 10a7 7 0 0 1-14 0"/>
                  <line x1="12" y1="19" x2="12" y2="23"/>
                  <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
              )}
            </button>
          </div>
          {status === 'recording' && <div className="rec-timer">{timer}</div>}
          {status !== 'recording' && !blob && <span className="rec-hint">Tap to start recording</span>}
          {blob && status === 'idle' && <span className="rec-ready">✓ Ready · {(blob.size/1024).toFixed(0)} KB</span>}
        </div>

        {status === 'processing' && (
          <div className="process-steps">
            {STEPS.map((step, i) => (
              <div key={step.key} className={`process-step ${i < stepIdx ? 'done' : i === stepIdx ? 'active' : ''}`}>
                <div className="step-dot">{i < stepIdx ? '✓' : i === stepIdx ? <div className="spin-dot"/> : '·'}</div>
                <span>{step.label}</span>
              </div>
            ))}
          </div>
        )}

        {status === 'error' && errMsg && <div className="error-banner">⚠ {errMsg}</div>}

        <button className="submit-btn" onClick={submit} disabled={!blob || status === 'processing' || status === 'recording'}>
          {status === 'processing' ? '⏳  Processing...' : '→  Submit Incident'}
        </button>
      </div>
    </>
  )
}
import { useState, useRef, useEffect } from 'react'
import { processAudio } from '../lib/api'

const STEPS = [
  { key: 'transcribe', label: 'Transcribing audio via VALSEA' },
  { key: 'sentiment',  label: 'Analysing sentiment'           },
  { key: 'prosody',    label: 'Detecting urgency & stress'    },
  { key: 'format',     label: 'Extracting action items'       },
  { key: 'save',       label: 'Saving to ResQNet'             },
]

const PRIORITY_COLOURS = {
  critical: 'var(--p-critical)',
  high:     'var(--p-high)',
  medium:   'var(--p-medium)',
  low:      'var(--p-low)',
}

function useTimer(running) {
  const [secs, setSecs] = useState(0)
  useEffect(() => {
    if (!running) { setSecs(0); return }
    const id = setInterval(() => setSecs(s => s + 1), 1000)
    return () => clearInterval(id)
  }, [running])
  return `${String(Math.floor(secs / 60)).padStart(2,'0')}:${String(secs % 60).padStart(2,'0')}`
}

export default function AudioRecorder({ onIncidentCreated }) {
  const [name,      setName]      = useState('')
  const [location,  setLocation]  = useState('')
  const [status,    setStatus]    = useState('idle')   // idle|recording|processing|success|error
  const [blob,      setBlob]      = useState(null)
  const [stepIdx,   setStepIdx]   = useState(0)
  const [errMsg,    setErrMsg]    = useState('')
  const [priority,  setPriority]  = useState(null)

  const mrRef     = useRef(null)
  const chunksRef = useRef([])
  const timer     = useTimer(status === 'recording')

  async function startRec() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = () => {
        setBlob(new Blob(chunksRef.current, { type: 'audio/webm' }))
        stream.getTracks().forEach(t => t.stop())
      }
      mr.start(250)
      mrRef.current = mr
      setStatus('recording')
    } catch {
      setStatus('error')
      setErrMsg('Microphone access denied. Please allow mic access and try again.')
    }
  }

  function stopRec() {
    mrRef.current?.stop()
    setStatus('idle')
  }

  async function submit() {
    if (!blob) return
    setStatus('processing')
    setStepIdx(0)
    setErrMsg('')

    let i = 0
    const t = setInterval(() => {
      i++
      if (i < STEPS.length) setStepIdx(i)
      else clearInterval(t)
    }, 2600)

    try {
      const data = await processAudio(blob, {
        caller_name: name || 'Unknown',
        location: location || 'Unknown',
      })
      clearInterval(t)

      setPriority(data.priority)
      setStatus('success')
      onIncidentCreated?.()
    } catch (e) {
      clearInterval(t)
      setErrMsg(e.message || 'Something went wrong. Please try again.')
      setStatus('error')
    }
  }

  function reset() {
    setStatus('idle'); setBlob(null)
    setName(''); setLocation('')
    setStepIdx(0); setErrMsg(''); setPriority(null)
  }

  /* ── Success ─────────────────────────────── */
  if (status === 'success') {
    return (
      <>
        <div className="section-label">
          <span className="section-label-text">New Incident</span>
          <span className="section-label-line" />
        </div>
        <div className="success-card">
          <div className="success-icon">✅</div>
          <div className="success-title">Incident Logged</div>
          {priority && (
            <div className="p-badge" style={{
              background: `${PRIORITY_COLOURS[priority]}18`,
              border: `1px solid ${PRIORITY_COLOURS[priority]}44`,
              color: PRIORITY_COLOURS[priority],
              fontSize: 11, padding: '6px 14px'
            }}>
              ● {priority?.toUpperCase()} PRIORITY
            </div>
          )}
          <div className="success-sub">Visible on the live dashboard now.</div>
          <button className="reset-btn" onClick={reset}>+ Log Another</button>
        </div>
      </>
    )
  }

  /* ── Main Form ───────────────────────────── */
  return (
    <>
      <div className="section-label">
        <span className="section-label-text">New Incident</span>
        <span className="section-label-line" />
      </div>

      <div className="incident-form">

        <div className="form-row">
          <label className="form-label">Caller Name</label>
          <input
            className="form-input"
            placeholder="e.g. Priya Nair"
            value={name}
            onChange={e => setName(e.target.value)}
            disabled={status === 'processing'}
          />
        </div>

        <div className="form-row">
          <label className="form-label">Location</label>
          <input
            className="form-input"
            placeholder="e.g. Batticaloa, Eastern Province"
            value={location}
            onChange={e => setLocation(e.target.value)}
            disabled={status === 'processing'}
          />
        </div>

        {/* Record zone */}
        <div className="record-zone">
          <div className="waveform">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className={`wv-bar ${status === 'recording' ? 'active' : ''}`} />
            ))}
          </div>

          <div className={`rec-btn-wrap ${status === 'recording' ? 'recording' : ''}`}>
            <div className="rec-btn-ring" />
            <button
              className={`rec-btn ${status === 'recording' ? 'recording' : ''}`}
              onClick={status === 'recording' ? stopRec : startRec}
              disabled={status === 'processing'}
              title={status === 'recording' ? 'Stop recording' : 'Start recording'}
            >
              {status === 'recording' ? (
                /* Stop icon */
                <svg width="20" height="20" viewBox="0 0 20 20" fill="var(--p-critical)">
                  <rect x="3" y="3" width="14" height="14" rx="3"/>
                </svg>
              ) : (
                /* Mic icon */
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                     stroke="var(--txt-secondary)" strokeWidth="1.8"
                     strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4z"/>
                  <path d="M19 10a7 7 0 0 1-14 0"/>
                  <line x1="12" y1="19" x2="12" y2="23"/>
                  <line x1="8"  y1="23" x2="16" y2="23"/>
                </svg>
              )}
            </button>
          </div>

          {status === 'recording' && (
            <div className="rec-timer">{timer}</div>
          )}

          {status !== 'recording' && !blob && (
            <span className="rec-hint">Tap to start recording</span>
          )}

          {blob && status === 'idle' && (
            <span className="rec-ready">
              ✓ Ready · {(blob.size / 1024).toFixed(0)} KB
            </span>
          )}
        </div>

        {/* Processing */}
        {status === 'processing' && (
          <div className="process-steps">
            {STEPS.map((step, i) => {
              const cls = i < stepIdx ? 'done' : i === stepIdx ? 'active' : ''
              return (
                <div key={step.key} className={`process-step ${cls}`}>
                  <div className="step-dot">
                    {i < stepIdx  ? '✓' :
                     i === stepIdx ? <div className="spin-dot" /> : '·'}
                  </div>
                  <span>{step.label}</span>
                </div>
              )
            })}
          </div>
        )}

        {/* Error */}
        {status === 'error' && errMsg && (
          <div className="error-banner">⚠ {errMsg}</div>
        )}

        <button
          className="submit-btn"
          onClick={submit}
          disabled={!blob || status === 'processing' || status === 'recording'}
        >
          {status === 'processing' ? '⏳  Processing...' : '→  Submit Incident'}
        </button>
      </div>
    </>
  )
}
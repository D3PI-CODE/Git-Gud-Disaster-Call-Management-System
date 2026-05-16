import { useState, useRef, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const STEPS = [
  { key: 'transcribe',  label: 'Transcribing audio...' },
  { key: 'sentiment',   label: 'Analysing sentiment...' },
  { key: 'prosody',     label: 'Detecting urgency & stress...' },
  { key: 'formatting',  label: 'Extracting action items...' },
  { key: 'saving',      label: 'Saving to dashboard...' },
]

function useTimer(active) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    if (!active) { setSeconds(0); return }
    const id = setInterval(() => setSeconds(s => s + 1), 1000)
    return () => clearInterval(id)
  }, [active])
  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

export default function AudioRecorder() {
  const [callerName, setCallerName] = useState('')
  const [location,   setLocation]   = useState('')

  // States: idle | recording | processing | success | error
  const [status,    setStatus]    = useState('idle')
  const [audioBlob, setAudioBlob] = useState(null)
  const [stepIndex, setStepIndex] = useState(0)
  const [errorMsg,  setErrorMsg]  = useState('')
  const [priority,  setPriority]  = useState(null)

  const mediaRecorderRef = useRef(null)
  const chunksRef        = useRef([])
  const timer = useTimer(status === 'recording')

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []

      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setAudioBlob(blob)
        stream.getTracks().forEach(t => t.stop())
      }

      mr.start(250)
      mediaRecorderRef.current = mr
      setStatus('recording')
    } catch (err) {
      console.error('Failed to access microphone:', err)
      setStatus('error')
      setErrorMsg('Microphone access denied. Please allow microphone access.')
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop()
    setStatus('idle') // will be updated to 'processing' via submit
  }

  async function handleSubmit() {
    if (!audioBlob) return
    setStatus('processing')
    setStepIndex(0)
    setErrorMsg('')

    // Simulate step progression while waiting for the API
    let step = 0
    const stepTimer = setInterval(() => {
      step++
      if (step < STEPS.length) setStepIndex(step)
      else clearInterval(stepTimer)
    }, 2800)

    try {
      const form = new FormData()
      form.append('audio',       new File([audioBlob], 'call.webm', { type: 'audio/webm' }))
      form.append('caller_name', callerName || 'Unknown')
      form.append('location',    location   || 'Unknown')

      const res  = await fetch(`${API_URL}/incident`, { method: 'POST', body: form })
      clearInterval(stepTimer)

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Server error ${res.status}`)
      }

      const data = await res.json()
      setPriority(data.priority)
      setStatus('success')
    } catch (err) {
      clearInterval(stepTimer)
      setErrorMsg(err.message || 'Something went wrong. Try again.')
      setStatus('error')
    }
  }

  function reset() {
    setStatus('idle')
    setAudioBlob(null)
    setCallerName('')
    setLocation('')
    setStepIndex(0)
    setErrorMsg('')
    setPriority(null)
  }

  // ─── Render ───────────────────────────────────────────────

  if (status === 'success') {
    const PRIORITY_ICONS = { critical:'🔴', high:'🟠', medium:'🟡', low:'🟢' }
    return (
      <>
        <div className="panel-title">New Incident</div>
        <div className="success-state">
          <div className="success-icon">✅</div>
          <div className="success-title">Incident Logged</div>
          {priority && (
            <div className={`priority-badge ${priority}`} style={{ fontSize: 12, padding: '5px 12px' }}>
              {PRIORITY_ICONS[priority]} {priority?.toUpperCase()} PRIORITY
            </div>
          )}
          <div className="success-sub">
            The incident has appeared on the live dashboard.
          </div>
          <button className="reset-btn" onClick={reset}>+ Log Another</button>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="panel-title">New Incident</div>

      <div className="recorder-form">
        {/* Caller Name */}
        <div className="field-group">
          <label className="field-label">Caller Name</label>
          <input
            className="field-input"
            placeholder="e.g. Priya Nair"
            value={callerName}
            onChange={e => setCallerName(e.target.value)}
            disabled={status === 'processing'}
          />
        </div>

        {/* Location */}
        <div className="field-group">
          <label className="field-label">Location</label>
          <input
            className="field-input"
            placeholder="e.g. Batticaloa, Eastern Province"
            value={location}
            onChange={e => setLocation(e.target.value)}
            disabled={status === 'processing'}
          />
        </div>

        {/* Record Area */}
        <div className="record-area">
          {/* Waveform (visible while recording) */}
          <div className="waveform">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className={`wave-bar ${status === 'recording' ? 'active' : ''}`}
                style={{ height: status !== 'recording' ? 4 : undefined }}
              />
            ))}
          </div>

          {/* Mic / Stop button */}
          <button
            className={`record-btn ${status === 'recording' ? 'recording' : ''}`}
            onClick={status === 'recording' ? stopRecording : startRecording}
            disabled={status === 'processing'}
            title={status === 'recording' ? 'Stop recording' : 'Start recording'}
          >
            {status === 'recording' ? (
              /* Stop icon */
              <svg width="22" height="22" viewBox="0 0 24 24" fill="var(--critical)">
                <rect x="4" y="4" width="16" height="16" rx="2" />
              </svg>
            ) : (
              /* Mic icon */
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                   stroke="var(--text-secondary)" strokeWidth="2"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4z"/>
                <path d="M19 10a7 7 0 0 1-14 0"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8"  y1="23" x2="16" y2="23"/>
              </svg>
            )}
          </button>

          {/* Timer */}
          {status === 'recording' && (
            <div className="record-timer">{timer}</div>
          )}

          {/* Hint text */}
          {status === 'idle' && !audioBlob && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Tap to start recording
            </span>
          )}

          {audioBlob && status === 'idle' && (
            <span style={{ fontSize: 11, color: 'var(--low)', fontFamily: 'var(--font-mono)' }}>
              ✓ Recording ready ({(audioBlob.size / 1024).toFixed(0)} KB)
            </span>
          )}
        </div>

        {/* Processing steps */}
        {status === 'processing' && (
          <div className="processing-steps">
            {STEPS.map((step, i) => {
              const state = i < stepIndex ? 'done' : i === stepIndex ? 'active' : ''
              return (
                <div key={step.key} className={`step-row ${state}`}>
                  <div className="step-icon">
                    {i < stepIndex  ? '✓' :
                     i === stepIndex ? <div className="spinner" /> :
                     '·'}
                  </div>
                  <span>{step.label}</span>
                </div>
              )
            })}
          </div>
        )}

        {/* Error */}
        {status === 'error' && errorMsg && (
          <div className="error-msg">⚠ {errorMsg}</div>
        )}

        {/* Submit */}
        <button
          className="submit-btn"
          onClick={handleSubmit}
          disabled={!audioBlob || status === 'processing' || status === 'recording'}
        >
          {status === 'processing' ? '⏳ Processing...' : '→ Submit Incident'}
        </button>
      </div>
    </>
  )
}
const SESSION_LABELS = {
  'Race':              'RACE',
  'Sprint':            'SPRINT',
  'Qualifying':        'QUALI',
  'Sprint Qualifying': 'S-QUALI',
  'Sprint Shootout':   'S-QUALI',
  'Practice 1':        'FP1',
  'Practice 2':        'FP2',
  'Practice 3':        'FP3',
}

function isRaceLike(sessionType) {
  const s = (sessionType ?? '').toLowerCase()
  return s === 'race' || s === 'sprint'
}

function useIsStale(lastUpdated, thresholdMs = 30000) {
  if (!lastUpdated) return false
  return Date.now() - new Date(lastUpdated).getTime() > thresholdMs
}

export default function Header({ data }) {
  const label   = SESSION_LABELS[data.session_type] ?? data.session_type ?? 'RACE'
  const showLap = isRaceLike(data.session_type) && data.lap_number != null
  const stale   = useIsStale(data.last_updated)

  return (
    <header className="header">
      <div className="header-left">
        <span className="f1-logo">F1</span>
        <h1 className="race-name">{data.meeting ?? 'Loading…'}</h1>
        <span className="session-tag">{label}</span>
      </div>
      <div className="header-right">
        {stale && data.is_live && (
          <span className="stale-badge" title="No data received in 30s">⚠ STALE</span>
        )}
        {showLap && (
          <span className="lap-counter">LAP {data.lap_number}</span>
        )}
        <span className={`status-badge ${data.is_live ? 'live' : 'finished'}`}>
          {data.is_live ? '● LIVE' : 'FINISHED'}
        </span>
      </div>
    </header>
  )
}

function isRaceLike(sessionType) {
  const s = (sessionType ?? '').toLowerCase()
  return s === 'race' || s === 'sprint'
}

export default function SessionInfoBar({ data }) {
  const { session_type, lap_number, total_laps, session_remaining, is_live } = data ?? {}

  if (isRaceLike(session_type)) {
    if (lap_number == null) return null
    return (
      <div className="session-info-bar">
        <span className="sib-label">LAP</span>
        <span className="sib-value">
          {lap_number}
          {total_laps != null && (
            <span className="sib-total"> / {total_laps}</span>
          )}
        </span>
      </div>
    )
  }

  // FP / Qualifying — only meaningful when live and clock data has arrived
  if (!is_live || !session_remaining) return null

  return (
    <div className="session-info-bar">
      <span className="sib-label">TIME LEFT</span>
      <span className="sib-value">{session_remaining}</span>
    </div>
  )
}

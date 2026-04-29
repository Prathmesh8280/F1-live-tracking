export default function Header({ data }) {
  return (
    <header className="header">
      <div className="header-left">
        <span className="f1-logo">F1</span>
        <h1 className="race-name">{data.meeting ?? 'Loading…'}</h1>
      </div>
      <div className="header-right">
        {data.lap_number != null && (
          <span className="lap-counter">LAP {data.lap_number}</span>
        )}
        <span className={`status-badge ${data.is_live ? 'live' : 'finished'}`}>
          {data.is_live ? '● LIVE' : 'FINISHED'}
        </span>
      </div>
    </header>
  )
}

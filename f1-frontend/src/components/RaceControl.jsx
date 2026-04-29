function flagClass(flag, category, message) {
  if (!flag && !category) return 'default'
  const f = (flag ?? '').toUpperCase()
  const m = (message ?? '').toUpperCase()
  if (f === 'RED')    return 'red'
  if (f === 'YELLOW' || f === 'DOUBLE YELLOW') return 'yellow'
  if (m.includes('SAFETY CAR') && !m.includes('VIRTUAL')) return 'sc'
  if (m.includes('VIRTUAL SAFETY CAR') || m.includes('VSC')) return 'vsc'
  if (f === 'GREEN' || f === 'CLEAR') return 'clear'
  return 'default'
}

function flagLabel(flag, message) {
  const f = (flag ?? '').toUpperCase()
  const m = (message ?? '').toUpperCase()
  if (f === 'RED')    return 'RED FLAG'
  if (f === 'YELLOW') return 'YELLOW'
  if (f === 'DOUBLE YELLOW') return 'DBL YELLOW'
  if (m.includes('VIRTUAL SAFETY CAR') || m.includes('VSC')) return 'VSC'
  if (m.includes('SAFETY CAR')) return 'SC'
  if (f === 'GREEN' || f === 'CLEAR') return 'GREEN'
  return null
}

function fmtTime(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function RaceControl({ messages }) {
  if (!messages?.length) return null

  const recent = [...messages].reverse().slice(0, 20)

  return (
    <div className="race-control">
      <div className="race-control-header">RACE CONTROL</div>
      <div className="rc-messages">
        {recent.map((msg, i) => {
          const cls   = flagClass(msg.flag, msg.category, msg.message)
          const label = flagLabel(msg.flag, msg.message)
          return (
            <div key={i} className="rc-message">
              <span className="rc-time">{fmtTime(msg.date)}</span>
              {label && <span className={`rc-flag ${cls}`}>{label}</span>}
              <span className="rc-text">{msg.message}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ── Flag SVG components ─────────────────────────────────────────── */

function FlagBase({ children, poleColor = '#888' }) {
  return (
    <svg width="26" height="20" viewBox="0 0 26 20" fill="none"
      aria-hidden="true" style={{ flexShrink: 0 }}>
      <line x1="2" y1="0" x2="2" y2="20" stroke={poleColor} strokeWidth="1.8" strokeLinecap="round"/>
      {children}
    </svg>
  )
}

function YellowFlag() {
  return (
    <FlagBase>
      <rect x="2" y="1.5" width="22" height="13" fill="#fbbf24" rx="1"/>
    </FlagBase>
  )
}

function RedFlag() {
  return (
    <FlagBase>
      <rect x="2" y="1.5" width="22" height="13" fill="#ef4444" rx="1"/>
    </FlagBase>
  )
}

function GreenFlag() {
  return (
    <FlagBase>
      <rect x="2" y="1.5" width="22" height="13" fill="#34d399" rx="1"/>
    </FlagBase>
  )
}

function ChequeredFlag() {
  const cols = 4, cw = 5.5, ch = 6.5
  return (
    <FlagBase poleColor="#aaa">
      {[0,1,2,3].flatMap(col => [0,1].map(row => (
        <rect key={`${col}-${row}`}
          x={2 + col * cw} y={1.5 + row * ch}
          width={cw} height={ch}
          fill={(col + row) % 2 === 0 ? '#ffffff' : '#111111'}
        />
      )))}
    </FlagBase>
  )
}

function SCFlag() {
  return (
    <FlagBase>
      <rect x="2" y="1.5" width="22" height="13" fill="#fb923c" rx="1"/>
      <text x="13" y="9.5" textAnchor="middle" dominantBaseline="middle"
        fill="#000" fontSize="6" fontWeight="800"
        fontFamily="system-ui, sans-serif" letterSpacing="0.8">SC</text>
    </FlagBase>
  )
}

function VSCFlag() {
  return (
    <FlagBase>
      <rect x="2" y="1.5" width="22" height="13" fill="#fdba74" rx="1"/>
      <text x="13" y="9.5" textAnchor="middle" dominantBaseline="middle"
        fill="#000" fontSize="5" fontWeight="800"
        fontFamily="system-ui, sans-serif" letterSpacing="0.5">VSC</text>
    </FlagBase>
  )
}

const FLAG_COMPONENTS = {
  yellow:    YellowFlag,
  red:       RedFlag,
  green:     GreenFlag,
  chequered: ChequeredFlag,
  sc:        SCFlag,
  vsc:       VSCFlag,
}

/* ── Banner logic ────────────────────────────────────────────────── */

function getActiveBanner(messages) {
  if (!messages?.length) return null

  const sorted = [...messages].sort((a, b) => new Date(b.date) - new Date(a.date))

  for (const msg of sorted) {
    const flag  = (msg.flag    ?? '').toUpperCase().trim()
    const text  = (msg.message ?? '').toUpperCase()
    const scope = (msg.scope   ?? '').toUpperCase()

    if (scope === 'DRIVER') continue

    if (flag === 'RED')
      return { type: 'red',       label: 'RED FLAG',    msg }
    if (flag === 'YELLOW')
      return { type: 'yellow',    label: 'YELLOW FLAG', msg }
    if (flag === 'DOUBLE YELLOW')
      return { type: 'yellow',    label: 'DBL YELLOW',  msg }
    if (text.includes('VIRTUAL SAFETY CAR') || text.includes('VSC DEPLOYED'))
      return { type: 'vsc',       label: 'VIRTUAL SC',  msg }
    if (text.includes('SAFETY CAR DEPLOYED') || text.includes('SAFETY CAR IN'))
      return { type: 'sc',        label: 'SAFETY CAR',  msg }
    if (flag === 'CHEQUERED')
      return { type: 'chequered', label: 'CHEQUERED',   msg }
    if (flag === 'GREEN' || flag === 'CLEAR')
      return { type: 'green',     label: 'GREEN FLAG',  msg }
  }

  return null
}

function fmtTime(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function RaceBanner({ messages }) {
  const state = getActiveBanner(messages)
  if (!state) return null

  const FlagIcon = FLAG_COMPONENTS[state.type]

  return (
    <div className={`race-banner race-banner--${state.type}`}>
      <FlagIcon />
      <span className="race-banner-badge">{state.label}</span>
      <span className="race-banner-text">{state.msg.message}</span>
      <span className="race-banner-time">{fmtTime(state.msg.date)}</span>
    </div>
  )
}

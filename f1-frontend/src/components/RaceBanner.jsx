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

// TrackStatus codes from F1 live feed:
// 1=Clear, 2=Yellow, 3=SCDeploying, 4=SafetyCar, 5=Red, 6=VSCDeployed, 7=VSCEnding
function getActiveBanner(messages, trackStatus) {
  const sorted = messages?.length
    ? [...messages].sort((a, b) => new Date(b.date) - new Date(a.date))
    : []
  const hasChequered = messages?.some(m => (m.flag ?? '').toUpperCase().trim() === 'CHEQUERED')
  const ts = String(trackStatus ?? '')

  // TrackStatus is the authoritative source — use it first
  if (ts === '5') {
    const msg = sorted.find(m => (m.flag ?? '').toUpperCase() === 'RED') ?? {}
    return { type: 'red', label: 'RED FLAG', msg }
  }
  if (ts === '4') {
    const msg = sorted.find(m => (m.message ?? '').toUpperCase().includes('SAFETY CAR')) ?? {}
    return { type: 'sc', label: 'SAFETY CAR', msg }
  }
  if (ts === '3') {
    // SC dispatched but not yet on track — distinct label so it's not misleading
    const msg = sorted.find(m => (m.message ?? '').toUpperCase().includes('SAFETY CAR')) ?? {}
    return { type: 'sc', label: 'SC DEPLOYED', msg }
  }
  if (ts === '6') {
    const msg = sorted.find(m => {
      const t = (m.message ?? '').toUpperCase()
      return t.includes('VIRTUAL SAFETY CAR') || t.includes('VSC')
    }) ?? {}
    return { type: 'vsc', label: 'VIRTUAL SC', msg }
  }
  if (ts === '7') {
    return { type: 'vsc', label: 'VSC ENDING', msg: {} }
  }
  if (ts === '2') {
    const msg = sorted.find(m => {
      const f = (m.flag ?? '').toUpperCase().trim()
      return f === 'YELLOW' || f === 'DOUBLE YELLOW'
    }) ?? {}
    return { type: 'yellow', label: 'YELLOW FLAG', msg }
  }

  if (!sorted.length) return null

  // Message-based fallback — covers latency gaps where trackStatus hasn't updated yet
  for (const msg of sorted) {
    const flag  = (msg.flag    ?? '').toUpperCase().trim()
    const scope = (msg.scope   ?? '').toUpperCase()
    const text  = (msg.message ?? '').toUpperCase()
    if (scope === 'DRIVER') continue

    if (text.includes('VIRTUAL SAFETY CAR') || text.includes('VSC'))
      return { type: 'vsc',       label: 'VIRTUAL SC',  msg }
    if (text.includes('SAFETY CAR'))
      return { type: 'sc',        label: 'SAFETY CAR',  msg }
    if (flag === 'DOUBLE YELLOW')
      return { type: 'yellow',    label: 'DBL YELLOW',  msg }
    if (flag === 'YELLOW')
      return { type: 'yellow',    label: 'YELLOW FLAG', msg }
    if (flag === 'CHEQUERED')
      return { type: 'chequered', label: 'CHEQUERED',   msg }
    if ((flag === 'GREEN' || flag === 'CLEAR') && !hasChequered)
      return { type: 'green',     label: 'GREEN FLAG',  msg }
  }

  return null
}

function fmtTime(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function RaceBanner({ messages, isLive, trackStatus }) {
  const state = !isLive
    ? { type: 'chequered', label: 'CHEQUERED', msg: {} }
    : getActiveBanner(messages, trackStatus)
  if (!state) return null

  const FlagIcon = FLAG_COMPONENTS[state.type]

  return (
    <div className={`race-banner race-banner--${state.type}`}>
      <FlagIcon />
      <span className="race-banner-badge">{state.label}</span>
      <span className="race-banner-text">{state.msg.message}</span>
    </div>
  )
}

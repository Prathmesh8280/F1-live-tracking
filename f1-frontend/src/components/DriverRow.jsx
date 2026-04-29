const TYRE_COLOR = {
  SOFT:         '#e8002d',
  MEDIUM:       '#ffd700',
  HARD:         '#f0f0f0',
  INTERMEDIATE: '#39b54a',
  WET:          '#0067ff',
}

const TYRE_ABBR = {
  SOFT:         'S',
  MEDIUM:       'M',
  HARD:         'H',
  INTERMEDIATE: 'I',
  WET:          'W',
}

function fmtTime(seconds) {
  if (seconds == null) return '–'
  if (seconds >= 60) {
    const m = Math.floor(seconds / 60)
    const s = (seconds % 60).toFixed(3).padStart(6, '0')
    return `${m}:${s}`
  }
  return seconds.toFixed(3)
}

function parseGap(interval) {
  if (!interval) return { type: 'none' }
  const raw = interval.gap_to_leader

  if (raw == null) return { type: 'none' }

  const str = String(raw).trim().toUpperCase()

  if (str === 'DNF') return { type: 'dnf' }

  // Lapped: "+1 LAP", "+2 LAPS"
  if (str.includes('LAP')) return { type: 'lapped', label: str }

  const n = parseFloat(raw)
  if (isNaN(n)) return { type: 'none' }
  if (n === 0)  return { type: 'leader' }
  return { type: 'gap', label: `+${n.toFixed(3)}` }
}

export default function DriverRow({ row }) {
  const { position, driver, interval, tyre, tyreAge, sector, isDnf } = row
  const compound  = tyre?.compound?.toUpperCase()
  const tyreColor = compound ? (TYRE_COLOR[compound] ?? '#888') : null
  const tyreAbbr  = compound ? (TYRE_ABBR[compound]  ?? compound[0]) : '?'

  const gap = parseGap(interval)

  const gapLabel =
    gap.type === 'leader'  ? 'LEADER' :
    gap.type === 'gap'     ? gap.label :
    gap.type === 'lapped'  ? gap.label :
    gap.type === 'dnf'     ? 'DNF'    : '–'

  return (
    <tr className={`driver-row${isDnf ? ' dnf' : ''}`}>
      <td className="col-pos">{isDnf ? '–' : position}</td>

      <td className="col-driver">
        <span className="team-bar" style={{ background: driver.team_color ?? '#555' }} />
        <span className="driver-code">{driver.code ?? `#${driver.number}`}</span>
      </td>

      <td className={`col-gap${isDnf ? ' gap-dnf' : ''}`}>{gapLabel}</td>

      <td className="col-tyre">
        {tyre && !isDnf ? (
          <span className="tyre-badge" style={{ borderColor: tyreColor, color: tyreColor }}>
            {tyreAbbr}
            {tyreAge != null && <span className="tyre-age">{tyreAge}</span>}
          </span>
        ) : '–'}
      </td>

      <td className="col-sector">{isDnf ? '–' : fmtTime(sector?.sector_1)}</td>
      <td className="col-sector">{isDnf ? '–' : fmtTime(sector?.sector_2)}</td>
      <td className="col-sector">{isDnf ? '–' : fmtTime(sector?.sector_3)}</td>
      <td className="col-laptime">{isDnf ? '–' : fmtTime(sector?.lap_time)}</td>
      <td className="col-laptime">{isDnf ? '–' : fmtTime(sector?.best_lap_time)}</td>
    </tr>
  )
}

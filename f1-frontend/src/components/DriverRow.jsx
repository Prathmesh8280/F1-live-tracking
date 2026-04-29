const TYRE_COLOR = {
  SOFT:         '#e8002d',
  MEDIUM:       '#ffd700',
  HARD:         '#f0f0f0',
  INTERMEDIATE: '#39b54a',
  WET:          '#0067ff',
}

const TYRE_TEXT = {
  SOFT:         '#fff',
  MEDIUM:       '#000',
  HARD:         '#000',
  INTERMEDIATE: '#fff',
  WET:          '#fff',
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
  if (str.includes('LAP')) return { type: 'lapped', label: str }

  const n = parseFloat(raw)
  if (isNaN(n)) return { type: 'none' }
  if (n === 0)  return { type: 'leader' }
  return { type: 'gap', label: `+${n.toFixed(3)}` }
}

function fmtIntervalToAhead(interval) {
  if (!interval) return '–'
  const raw = interval.interval
  if (raw == null) return '–'
  const str = String(raw).trim().toUpperCase()
  if (str === 'DNF') return '–'
  if (str.includes('LAP')) return str
  const n = parseFloat(raw)
  if (isNaN(n)) return '–'
  if (n === 0) return '–'
  return `+${n.toFixed(3)}`
}

// purple = overall best, green = personal best, yellow = normal
function sectorClass(time, personalBest, overallBest) {
  if (time == null) return ''
  if (overallBest != null && time <= overallBest) return 'sector-purple'
  if (personalBest != null && time <= personalBest) return 'sector-green'
  return 'sector-yellow'
}

export default function DriverRow({ row, overallBest }) {
  const { position, driver, interval, tyre, tyreAge, tyreHistory, sector, isDnf, isPitting } = row

  const gap = parseGap(interval)

  const gapLabel =
    gap.type === 'leader'  ? 'LEADER' :
    gap.type === 'gap'     ? gap.label :
    gap.type === 'lapped'  ? gap.label :
    gap.type === 'dnf'     ? 'DNF'    : '–'

  const intLabel = isDnf ? '–' : fmtIntervalToAhead(interval)

  return (
    <tr className={`driver-row${isDnf ? ' dnf' : ''}`}>
      <td className="col-pos">{isDnf ? '–' : position}</td>

      <td className="col-driver">
        <span className="team-bar" style={{ background: driver.team_color ?? '#555' }} />
        <span className="driver-code">{driver.code ?? `#${driver.number}`}</span>
        {isPitting && <span className="pit-badge">PIT</span>}
      </td>

      <td className={`col-gap${isDnf ? ' gap-dnf' : ''}`}>{gapLabel}</td>

      <td className="col-int">{intLabel}</td>

      <td className="col-tyre">
        {!isDnf && tyreHistory?.length > 0 ? (
          <div className="tyre-history">
            {[...tyreHistory].reverse().slice(0, 2).map((stint, i) => {
              const isCurrent = i === 0
              const cmp   = stint.compound?.toUpperCase()
              const bg    = cmp ? (TYRE_COLOR[cmp] ?? '#888') : '#888'
              const fg    = cmp ? (TYRE_TEXT[cmp]  ?? '#fff') : '#fff'
              const abbr  = cmp ? (TYRE_ABBR[cmp]  ?? cmp[0]) : '?'
              const age   = isCurrent
                ? tyreAge
                : stint.lap_end != null
                  ? (stint.tyre_age_at_start ?? 0) + (stint.lap_end - stint.lap_start)
                  : null
              return (
                <span key={i} className={`tyre-stint${isCurrent ? '' : ' tyre-past'}`}>
                  {age != null && <span className="tyre-laps">{age}</span>}
                  <span className="tyre-circle" style={{ background: bg, color: fg }}>
                    {abbr}
                  </span>
                </span>
              )
            })}
          </div>
        ) : '–'}
      </td>

      <td className={`col-sector ${!isDnf ? sectorClass(sector?.sector_1, sector?.best_sector_1, overallBest?.s1) : ''}`}>
        {isDnf ? '–' : fmtTime(sector?.sector_1)}
      </td>
      <td className={`col-sector ${!isDnf ? sectorClass(sector?.sector_2, sector?.best_sector_2, overallBest?.s2) : ''}`}>
        {isDnf ? '–' : fmtTime(sector?.sector_2)}
      </td>
      <td className={`col-sector ${!isDnf ? sectorClass(sector?.sector_3, sector?.best_sector_3, overallBest?.s3) : ''}`}>
        {isDnf ? '–' : fmtTime(sector?.sector_3)}
      </td>
      <td className={`col-laptime ${!isDnf ? sectorClass(sector?.lap_time, sector?.best_lap_time, overallBest?.lap) : ''}`}>
        {isDnf ? '–' : fmtTime(sector?.lap_time)}
      </td>
      <td className={`col-laptime ${!isDnf ? sectorClass(sector?.best_lap_time, sector?.best_lap_time, overallBest?.lap) : ''}`}>
        {isDnf ? '–' : fmtTime(sector?.best_lap_time)}
      </td>
    </tr>
  )
}

import DriverRow from './DriverRow'

/**
 * OpenF1 returns full history lists for intervals and tyres.
 * This function joins them into one flat object per driver, ready for rendering.
 */
function buildRows(positions, intervals, tyres, sectors, lapNumber) {
  // Latest interval per driver (by date string — ISO sorts lexicographically)
  const intervalMap = {}
  for (const iv of intervals ?? []) {
    const n = iv.driver_number
    if (!intervalMap[n] || iv.date > intervalMap[n].date) {
      intervalMap[n] = iv
    }
  }

  // Always pick the highest stint_number — that is always the most recent tyre.
  // (For live races the current stint has lap_end === null; for finished races
  // every stint has a lap_end, so the null-preference logic would wrongly keep
  // the very first stint for everyone.)
  const tyreMap = {}
  for (const stint of tyres ?? []) {
    const n = stint.driver_number
    const prev = tyreMap[n]
    if (!prev || stint.stint_number > prev.stint_number) {
      tyreMap[n] = stint
    }
  }

  return (positions ?? []).map((p) => {
    const n = p.driver.number
    const tyre = tyreMap[n]

    // Use lap_end when available (exact for finished stints); fall back to
    // the current lap number (estimate for an ongoing stint).
    const endLap = tyre?.lap_end ?? lapNumber
    const tyreAge =
      tyre != null && endLap != null
        ? (tyre.tyre_age_at_start ?? 0) + (endLap - tyre.lap_start)
        : null

    // sectors keys are strings in JSON (Python int keys → JSON string keys)
    const sector = sectors?.[n] ?? sectors?.[String(n)]

    // A driver is DNF if:
    // 1. OpenF1 explicitly returns "DNF" as the gap string, OR
    // 2. Their last completed lap is 3+ laps behind the race total
    //    (lapped drivers are typically only 1-2 laps down and still classified)
    const gapStr = String(intervalMap[n]?.gap_to_leader ?? '').trim().toUpperCase()
    const lapsBehind = sector?.lap_number != null && lapNumber != null
      ? lapNumber - sector.lap_number
      : 0
    const isDnf = gapStr === 'DNF' || lapsBehind > 2

    return { ...p, interval: intervalMap[n], tyre, tyreAge, sector, isDnf }
  })
}

export default function TimingTower({ data }) {
  const rows = buildRows(
    data.positions,
    data.intervals,
    data.tyres,
    data.sectors,
    data.lap_number,
  )

  if (rows.length === 0) {
    return <p className="no-data">No race data available yet.</p>
  }

  return (
    <div className="timing-tower">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>POS</th>
              <th>DRIVER</th>
              <th>GAP</th>
              <th>TYRE</th>
              <th>S1</th>
              <th>S2</th>
              <th>S3</th>
              <th>LAST LAP</th>
              <th>BEST LAP</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <DriverRow key={row.driver.number} row={row} />
            ))}
          </tbody>
        </table>
      </div>
      {data.last_updated && (
        <p className="last-updated">
          Updated {new Date(data.last_updated).toLocaleTimeString()}
        </p>
      )}
    </div>
  )
}

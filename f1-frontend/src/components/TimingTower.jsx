import DriverRow from './DriverRow'

function sessionCategory(sessionType) {
  if (!sessionType) return 'race'
  const s = sessionType.toLowerCase()
  if (s.includes('practice')) return 'practice'
  if (s.includes('qualifying')) return 'qualifying'
  if (s === 'sprint') return 'sprint'
  return 'race'
}

function buildRows(positions, intervals, tyres, sectors, pitStops, lapNumber, category) {
  const intervalMap = {}
  for (const iv of intervals ?? []) {
    const n = iv.driver_number
    if (!intervalMap[n] || iv.date > intervalMap[n].date) {
      intervalMap[n] = iv
    }
  }

  const tyreHistoryMap = {}
  for (const stint of tyres ?? []) {
    const n = stint.driver_number
    if (!tyreHistoryMap[n]) tyreHistoryMap[n] = []
    tyreHistoryMap[n].push(stint)
  }
  for (const n in tyreHistoryMap) {
    tyreHistoryMap[n].sort((a, b) => a.stint_number - b.stint_number)
  }

  const pitMap = {}
  for (const pit of pitStops ?? []) {
    if (pit.pit_duration == null) {
      pitMap[pit.driver_number] = true
    }
  }

  return (positions ?? []).map((p) => {
    const n = p.driver.number
    const history = tyreHistoryMap[n] ?? []
    const tyre = history[history.length - 1]

    const endLap = tyre?.lap_end ?? lapNumber
    const tyreAge =
      tyre != null && endLap != null
        ? (tyre.tyre_age_at_start ?? 0) + (endLap - tyre.lap_start)
        : null

    const sector = sectors?.[n] ?? sectors?.[String(n)]

    const gapStr = String(intervalMap[n]?.gap_to_leader ?? '').trim().toUpperCase()
    const isRaceLike = category === 'race' || category === 'sprint'
    const lapsBehind = isRaceLike && sector?.lap_number != null && lapNumber != null
      ? lapNumber - sector.lap_number
      : 0
    const isDnf = gapStr === 'DNF' || (isRaceLike && lapsBehind > 2)
    const isPitting = !isDnf && (pitMap[n] === true)

    return { ...p, interval: intervalMap[n], tyre, tyreAge, tyreHistory: history, sector, isDnf, isPitting }
  })
}

function minOf(rows, fn) {
  const vals = rows.map(fn).filter(v => v != null)
  return vals.length ? Math.min(...vals) : null
}

export default function TimingTower({ data }) {
  const category   = sessionCategory(data.session_type)
  const showGapInt = category === 'race' || category === 'sprint'

  const rows = buildRows(
    data.positions,
    data.intervals,
    data.tyres,
    data.sectors,
    data.pit_stops,
    data.lap_number,
    category,
  )

  if (rows.length === 0) {
    return <p className="no-data">No session data available yet.</p>
  }

  const overallBest = {
    s1:  minOf(rows, r => r.sector?.sector_1),
    s2:  minOf(rows, r => r.sector?.sector_2),
    s3:  minOf(rows, r => r.sector?.sector_3),
    lap: minOf(rows, r => r.sector?.best_lap_time),
  }

  return (
    <div className="timing-tower">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>POS</th>
              <th>DRIVER</th>
              {showGapInt && <th>GAP</th>}
              {showGapInt && <th>INT</th>}
              <th>TYRES</th>
              <th>S1</th>
              <th>S2</th>
              <th>S3</th>
              <th>LAST LAP</th>
              <th>BEST LAP</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <DriverRow
                key={row.driver.number}
                row={row}
                overallBest={overallBest}
                showGapInt={showGapInt}
              />
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

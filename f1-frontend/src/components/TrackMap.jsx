import { useState, useEffect, useCallback, useMemo } from 'react'
import { API_BASE } from '../config'
const SVG_W = 500
const SVG_H = 500
const PADDING = 10

const SECTOR_COLORS = ['#e8002d', '#ffd700', '#00aaff']  // S1 red, S2 yellow, S3 blue

function buildTransform(points) {
  if (!points.length) return null
  const xs = points.map(p => p.x)
  const ys = points.map(p => p.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minY = Math.min(...ys), maxY = Math.max(...ys)
  const rangeX = maxX - minX || 1
  const rangeY = maxY - minY || 1
  const innerW = SVG_W - PADDING * 2
  const innerH = SVG_H - PADDING * 2
  const scale  = Math.min(innerW / rangeX, innerH / rangeY)
  const offX   = PADDING + (innerW - rangeX * scale) / 2
  const offY   = PADDING + (innerH - rangeY * scale) / 2
  return {
    toSVG: (x, y) => ({
      x: offX + (x - minX) * scale,
      y: offY + (maxY - y) * scale,
    }),
  }
}

function toPolylinePoints(points, toSVG) {
  return points.map(p => {
    const s = toSVG(p.x, p.y)
    return `${s.x.toFixed(1)},${s.y.toFixed(1)}`
  }).join(' ')
}

/**
 * Split outline into three sector slices using time-based fractions.
 * We overlap by one point at each boundary to avoid visible gaps.
 */
function buildSectorPoints(outline, fractions, toSVG) {
  if (!fractions?.length || fractions.length < 2) {
    // No fraction data — fall back to equal thirds
    const n = outline.length
    return [
      toPolylinePoints(outline.slice(0, Math.floor(n / 3) + 1), toSVG),
      toPolylinePoints(outline.slice(Math.floor(n / 3), Math.floor(2 * n / 3) + 1), toSVG),
      toPolylinePoints(outline.slice(Math.floor(2 * n / 3)), toSVG),
    ]
  }
  const n   = outline.length
  const i1  = Math.floor(fractions[0] * n)
  const i2  = Math.floor(fractions[1] * n)
  return [
    toPolylinePoints(outline.slice(0, i1 + 1), toSVG),
    toPolylinePoints(outline.slice(i1, i2 + 1), toSVG),
    toPolylinePoints(outline.slice(i2), toSVG),
  ]
}

export default function TrackMap({ isLiveParent, positions }) {
  const [outline,  setOutline]  = useState([])
  const [fractions, setFractions] = useState([])
  const [carPos,   setCarPos]   = useState({})
  const [loading,  setLoading]  = useState(true)

  const fetchMap = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE}/race/map`)
      if (!res.ok) return
      const data = await res.json()
      if (data.track_outline?.length)  setOutline(data.track_outline)
      if (data.sector_fractions?.length) setFractions(data.sector_fractions)
      setCarPos(data.car_positions ?? {})
    } catch (_) {}
    finally { setLoading(false) }
  }, [])

  // Always fetch once on mount
  useEffect(() => { fetchMap() }, [fetchMap])

  // Live race: poll every 2s continuously
  useEffect(() => {
    if (!isLiveParent) return
    const id = setInterval(fetchMap, 2000)
    return () => clearInterval(id)
  }, [fetchMap, isLiveParent])

  // Finished race: keep retrying every 3s until background tasks have populated
  // all map data (track outline + car positions), then stop.
  const mapComplete = outline.length > 0 && Object.keys(carPos).length > 0
  useEffect(() => {
    if (isLiveParent || mapComplete) return
    const id = setInterval(fetchMap, 3000)
    return () => clearInterval(id)
  }, [fetchMap, isLiveParent, mapComplete])

  const transform = useMemo(() => buildTransform(outline), [outline])

  const sectorPoints = useMemo(() => {
    if (!transform || !outline.length) return []
    return buildSectorPoints(outline, fractions, transform.toSVG)
  }, [outline, fractions, transform])

  const drivers = useMemo(() => {
    if (!transform) return []
    // Build position lookup so leaders render on top (SVG: last element = topmost)
    const posMap = {}
    for (const p of positions ?? []) posMap[p.driver.number] = p.position ?? 999
    return Object.entries(carPos)
      .map(([num, d]) => {
        const { x, y } = transform.toSVG(d.x, d.y)
        return { num: Number(num), x, y, code: d.code, color: d.team_color ?? '#888', pos: posMap[Number(num)] ?? 999 }
      })
      .sort((a, b) => b.pos - a.pos)  // P20 first → P1 last (drawn on top)
  }, [carPos, transform, positions])

  // Checkered start/finish bar + direction arrow at outline[0]
  const startFinish = useMemo(() => {
    if (!transform || outline.length < 2) return null
    const p0 = transform.toSVG(outline[0].x, outline[0].y)
    const p1 = transform.toSVG(outline[1].x, outline[1].y)
    const dx = p1.x - p0.x
    const dy = p1.y - p0.y
    const len = Math.sqrt(dx * dx + dy * dy) || 1
    // Perpendicular angle for the checkered bar
    const barAngleDeg  = +(Math.atan2(dx, -dy) * (180 / Math.PI)).toFixed(1)
    // Arrow rotation: default arrow points up (-Y); rotate to match track direction
    const arrowAngleDeg = +(Math.atan2(dy, dx) * (180 / Math.PI) + 90).toFixed(1)
    // Place arrow to the left of the bar (perpendicular offset)
    const perpX = -dy / len
    const perpY =  dx / len
    return {
      cx: +p0.x.toFixed(1),
      cy: +p0.y.toFixed(1),
      barAngleDeg,
      arrowX: +(p0.x - perpX * 20).toFixed(1),
      arrowY: +(p0.y - perpY * 20).toFixed(1),
      arrowAngleDeg,
    }
  }, [outline, transform])

  return (
    <div className="track-map-card">
      <div className="track-map-header">
        <span className="track-map-title">TRACK MAP</span>
        <div className="sector-legend">
          {SECTOR_COLORS.map((c, i) => (
            <span key={i} className="sector-legend-item">
              <span className="sector-legend-dot" style={{ background: c }} />
              S{i + 1}
            </span>
          ))}
        </div>
        {isLiveParent && <span className="map-live-dot" />}
      </div>

      {loading ? (
        <div className="track-map-loading">Loading map…</div>
      ) : !outline.length ? (
        <div className="track-map-loading">No track data available</div>
      ) : (
        <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} className="track-svg" aria-label="F1 track map">

          {/* Dark border underneath everything */}
          <polyline points={toPolylinePoints(outline, transform.toSVG)}
            fill="none" stroke="#333" strokeWidth="12"
            strokeLinecap="round" strokeLinejoin="round" />

          {/* Sector-coloured centre lines */}
          {sectorPoints.map((pts, i) => (
            <polyline key={i} points={pts}
              fill="none" stroke={SECTOR_COLORS[i]} strokeWidth="5"
              strokeLinecap="round" strokeLinejoin="round" />
          ))}

          {/* Checkered start / finish bar + direction arrow */}
          {startFinish && (<>
            <g transform={`translate(${startFinish.cx},${startFinish.cy}) rotate(${startFinish.barAngleDeg})`}>
              {[0,1,2,3].map(col => [0,1].map(row => (
                <rect key={`${col}-${row}`}
                  x={-11 + col * 5.5} y={row === 0 ? -5 : 0}
                  width={5.5} height={5}
                  fill={(col + row) % 2 === 0 ? '#fff' : '#111'}
                />
              )))}
            </g>
            {/* Navigation-style direction arrow */}
            <g transform={`translate(${startFinish.arrowX},${startFinish.arrowY}) rotate(${startFinish.arrowAngleDeg})`}>
              <polygon points="0,-11 7,8 0,3 -7,8"
                fill="#fff" stroke="#0c0c0c" strokeWidth="1" strokeLinejoin="round" />
            </g>
          </>)}

          {/* Driver dots */}
          {drivers.map(d => (
            <g key={d.num} transform={`translate(${d.x.toFixed(1)}, ${d.y.toFixed(1)})`}>
              <circle r="11" fill={d.color} stroke="#0c0c0c" strokeWidth="1.5" />
              <text y="0" textAnchor="middle" dominantBaseline="central"
                fontSize="7" fontWeight="700" fill="#fff"
                style={{ fontFamily: 'system-ui, sans-serif', pointerEvents: 'none' }}>
                {d.code ?? `#${d.num}`}
              </text>
            </g>
          ))}
        </svg>
      )}
    </div>
  )
}

function Thermometer({ color }) {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>
    </svg>
  )
}

function Droplet() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="#38bdf8" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>
    </svg>
  )
}

function Wind() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="#a78bfa" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/>
      <path d="M9.6 4.6A2 2 0 1 1 11 8H2"/>
      <path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>
    </svg>
  )
}

function CloudRain() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="#38bdf8" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d="M20 17.58A5 5 0 0 0 18 8h-1.26A8 8 0 1 0 4 16.25"/>
      <line x1="8" y1="19" x2="8" y2="21"/>
      <line x1="16" y1="19" x2="16" y2="21"/>
      <line x1="12" y1="17" x2="12" y2="19"/>
    </svg>
  )
}

export default function WeatherStrip({ weather }) {
  if (!weather || Object.keys(weather).length === 0) return null

  const { air_temp, track_temp, humidity, wind_speed, wind_direction, rainfall } = weather

  return (
    <div className="weather-strip">
      {air_temp != null && (
        <span className="weather-item">
          <span className="weather-icon-group">
            <Thermometer color="#34d399" />
            <span className="weather-type-tag">A</span>
          </span>
          <span className="weather-value">{air_temp.toFixed(1)}°C</span>
        </span>
      )}
      {track_temp != null && (
        <span className="weather-item">
          <span className="weather-icon-group">
            <Thermometer color="#fb923c" />
            <span className="weather-type-tag">T</span>
          </span>
          <span className="weather-value">{track_temp.toFixed(1)}°C</span>
        </span>
      )}
      {humidity != null && (
        <span className="weather-item">
          <Droplet />
          <span className="weather-value">{humidity.toFixed(0)}%</span>
        </span>
      )}
      {wind_speed != null && (
        <span className="weather-item">
          <Wind />
          <span className="weather-value">
            {wind_speed.toFixed(1)} m/s{wind_direction != null ? ` ${wind_direction}°` : ''}
          </span>
        </span>
      )}
      {!!rainfall && (
        <span className="weather-item weather-rain">
          <CloudRain />
          <span>RAIN</span>
        </span>
      )}
    </div>
  )
}

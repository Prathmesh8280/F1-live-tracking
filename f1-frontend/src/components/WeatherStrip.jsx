export default function WeatherStrip({ weather }) {
  if (!weather || Object.keys(weather).length === 0) return null

  const { air_temp, track_temp, humidity, wind_speed, wind_direction, rainfall } = weather

  return (
    <div className="weather-strip">
      {air_temp != null && (
        <span className="weather-item">
          <span className="weather-label">AIR</span>
          <span className="weather-value">{air_temp.toFixed(1)}°C</span>
        </span>
      )}
      {track_temp != null && (
        <span className="weather-item">
          <span className="weather-label">TRACK</span>
          <span className="weather-value">{track_temp.toFixed(1)}°C</span>
        </span>
      )}
      {humidity != null && (
        <span className="weather-item">
          <span className="weather-label">HUMIDITY</span>
          <span className="weather-value">{humidity.toFixed(0)}%</span>
        </span>
      )}
      {wind_speed != null && (
        <span className="weather-item">
          <span className="weather-label">WIND</span>
          <span className="weather-value">{wind_speed.toFixed(1)} m/s {wind_direction != null ? `${wind_direction}°` : ''}</span>
        </span>
      )}
      {!!rainfall && (
        <span className="weather-item">
          <span className="weather-rain">🌧️ RAIN</span>
        </span>
      )}
    </div>
  )
}

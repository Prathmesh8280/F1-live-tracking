import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header'
import WeatherStrip from './components/WeatherStrip'
import TrackMap from './components/TrackMap'
import TimingTower from './components/TimingTower'
import { API_BASE } from './config'

function App() {
  const [data, setData]   = useState(null)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/race/timing_tower`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  // Always fetch once on mount
  useEffect(() => { fetchData() }, [fetchData])

  // Only poll while the race is live — finished races never change
  useEffect(() => {
    if (!data?.is_live) return
    const id = setInterval(fetchData, 2000)
    return () => clearInterval(id)
  }, [fetchData, data?.is_live])

  if (!data && !error) {
    return <div className="status-screen">Loading race data…</div>
  }
  if (error && !data) {
    return <div className="status-screen error">Could not reach backend: {error}</div>
  }

  return (
    <div className="app">
      <Header data={data} />
      <WeatherStrip weather={data?.weather} />
      <div className="main-grid">
        <TrackMap isLiveParent={data?.is_live} positions={data?.positions} />
        <TimingTower data={data} />
      </div>
    </div>
  )
}

export default App

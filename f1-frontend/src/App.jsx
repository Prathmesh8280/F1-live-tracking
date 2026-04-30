import { useState, useEffect, useRef, useCallback } from 'react'
import Header from './components/Header'
import WeatherStrip from './components/WeatherStrip'
import RaceBanner from './components/RaceBanner'
import SessionInfoBar from './components/SessionInfoBar'
import TrackMap from './components/TrackMap'
import TimingTower from './components/TimingTower'
import { WS_BASE } from './config'

const WS_URL = `${WS_BASE}/race/ws`
const RECONNECT_DELAY_MS = 3000

function App() {
  const [data,  setData]  = useState(null)
  const [error, setError] = useState(null)
  const wsRef      = useRef(null)
  const reconnectRef = useRef(null)

  const connect = useCallback(() => {
    // Don't double-connect
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setError(null)
    }

    ws.onmessage = (evt) => {
      try {
        setData(JSON.parse(evt.data))
      } catch {
        // malformed frame — ignore
      }
    }

    ws.onclose = () => {
      // Schedule reconnect unless the component is unmounting
      reconnectRef.current = setTimeout(connect, RECONNECT_DELAY_MS)
    }

    ws.onerror = () => {
      setError('Connection lost — reconnecting…')
      ws.close()
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  if (!data && !error) {
    return <div className="status-screen">Connecting…</div>
  }
  if (error && !data) {
    return <div className="status-screen error">{error}</div>
  }

  return (
    <div className="app">
      <Header data={data} />
      <div className="header-stripe" />
      <div className="main-grid">
        <div className="left-panel">
          <TrackMap isLiveParent={data?.is_live} positions={data?.positions} />
          <div className="panel-meta">
            <SessionInfoBar data={data} />
            <RaceBanner messages={data?.race_control} />
            <WeatherStrip weather={data?.weather} />
          </div>
        </div>
        <TimingTower data={data} />
      </div>
    </div>
  )
}

export default App

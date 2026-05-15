import { useState, useEffect, useRef, useCallback } from 'react'
import type { WSEvent } from '../types'

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const shouldReconnectRef = useRef(true)
  const connectRef = useRef<() => void>(() => {})

  const connect = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/dashboard`)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      retriesRef.current = 0
    }

    ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data)
        setLastEvent(event)
      } catch (error) {
        void error
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      wsRef.current = null
      if (!shouldReconnectRef.current) return
      const delay = Math.min(1000 * 2 ** retriesRef.current, 30000)
      retriesRef.current++
      reconnectTimeoutRef.current = window.setTimeout(() => {
        if (!shouldReconnectRef.current) return
        connectRef.current()
      }, delay)
    }

    ws.onerror = () => ws.close()
  }, [])

  useEffect(() => {
    shouldReconnectRef.current = true
    connectRef.current = connect
    connect()
    return () => {
      shouldReconnectRef.current = false
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      wsRef.current?.close()
    }
  }, [connect])

  return { isConnected, lastEvent }
}

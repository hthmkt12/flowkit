import { act, cleanup, render, renderHook, screen } from '@testing-library/react'
import { createElement, Fragment } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { dashboardWebSocketProtocols, useWebSocket } from './useWebSocket'

type ActEnvironmentGlobal = typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }

class MockWebSocket {
  static instances: MockWebSocket[] = []

  url: string
  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  protocols?: string | string[]

  constructor(url: string, protocols?: string | string[]) {
    this.url = url
    this.protocols = protocols
    MockWebSocket.instances.push(this)
  }

  emitOpen() {
    this.onopen?.(new Event('open'))
  }

  emitClose() {
    this.onclose?.(new CloseEvent('close'))
  }

  close() {
    this.emitClose()
  }
}

function PrimarySocketProbe() {
  const { isConnected } = useWebSocket()

  return createElement('span', { 'data-testid': 'primary-status' }, isConnected ? 'connected' : 'offline')
}

function SecondarySocketProbe() {
  const { isConnected } = useWebSocket()

  return createElement('span', { 'data-testid': 'secondary-status' }, isConnected ? 'connected' : 'offline')
}

function DualSocketProbe({ showSecondary }: { showSecondary: boolean }) {
  return createElement(
    Fragment,
    null,
    createElement(PrimarySocketProbe),
    showSecondary ? createElement(SecondarySocketProbe) : null,
  )
}

describe('useWebSocket', () => {
  beforeEach(() => {
    ;(globalThis as ActEnvironmentGlobal).IS_REACT_ACT_ENVIRONMENT = true
    MockWebSocket.instances = []
    window.localStorage.clear()
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket)
  })

  afterEach(() => {
    cleanup()
    expect(vi.getTimerCount()).toBe(0)
    ;(globalThis as ActEnvironmentGlobal).IS_REACT_ACT_ENVIRONMENT = false
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('reconnects after the socket closes', async () => {
    const { result } = renderHook(() => useWebSocket())

    expect(MockWebSocket.instances).toHaveLength(1)
    expect(MockWebSocket.instances[0].url).toMatch(/\/ws\/dashboard$/)
    expect(MockWebSocket.instances[0].protocols).toBeUndefined()

    act(() => {
      MockWebSocket.instances[0].emitOpen()
    })
    expect(result.current.isConnected).toBe(true)

    act(() => {
      MockWebSocket.instances[0].emitClose()
    })
    expect(result.current.isConnected).toBe(false)

    act(() => {
      vi.advanceTimersByTime(999)
    })
    expect(MockWebSocket.instances).toHaveLength(1)

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(MockWebSocket.instances).toHaveLength(2)

    act(() => {
      MockWebSocket.instances[1].emitOpen()
    })
    expect(result.current.isConnected).toBe(true)

    act(() => {
      MockWebSocket.instances[1].emitClose()
    })
    expect(result.current.isConnected).toBe(false)

    act(() => {
      vi.advanceTimersByTime(999)
    })
    expect(MockWebSocket.instances).toHaveLength(2)

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('uses bearer subprotocol when a browser demo token is configured', () => {
    window.localStorage.setItem('zoopostBearerToken', 'demo-token')

    expect(dashboardWebSocketProtocols()).toEqual(['bearer.b64.ZGVtby10b2tlbg'])
    vi.clearAllTimers()
  })

  it('encodes local API keys into browser-safe WebSocket subprotocols', () => {
    window.localStorage.setItem('zoopostBearerToken', 'abc+123/==')

    const protocols = dashboardWebSocketProtocols()

    expect(protocols).toEqual(['bearer.b64.YWJjKzEyMy89PQ'])
    expect(protocols?.[0]).toMatch(/^[A-Za-z0-9._-]+$/u)
    vi.clearAllTimers()
  })

  it('cancels a pending reconnect when the hook unmounts', () => {
    const { unmount } = renderHook(() => useWebSocket())

    act(() => {
      MockWebSocket.instances[0].emitClose()
    })

    unmount()

    act(() => {
      vi.runAllTimers()
    })

    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('ignores a queued reconnect callback after unmount', () => {
    let reconnectCallback: (() => void) | null = null

    vi.spyOn(window, 'setTimeout').mockImplementation(((callback: TimerHandler) => {
      reconnectCallback = callback as () => void
      return 1
    }) as typeof window.setTimeout)

    const clearTimeoutSpy = vi.spyOn(window, 'clearTimeout')
    const { unmount } = renderHook(() => useWebSocket())

    act(() => {
      MockWebSocket.instances[0].emitClose()
    })

    expect(reconnectCallback).not.toBeNull()

    unmount()

    expect(clearTimeoutSpy).toHaveBeenCalledWith(1)

    act(() => {
      reconnectCallback?.()
    })

    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('does not let an unmounted secondary consumer leak reconnects', () => {
    const { rerender } = render(createElement(DualSocketProbe, { showSecondary: true }))

    expect(MockWebSocket.instances).toHaveLength(2)

    act(() => {
      MockWebSocket.instances[0].emitOpen()
      MockWebSocket.instances[1].emitOpen()
    })

    expect(screen.getByTestId('primary-status').textContent).toBe('connected')
    expect(screen.getByTestId('secondary-status').textContent).toBe('connected')

    act(() => {
      MockWebSocket.instances[1].emitClose()
    })

    expect(screen.getByTestId('primary-status').textContent).toBe('connected')
    expect(screen.getByTestId('secondary-status').textContent).toBe('offline')

    rerender(createElement(DualSocketProbe, { showSecondary: false }))

    act(() => {
      vi.runAllTimers()
    })

    expect(MockWebSocket.instances).toHaveLength(2)
    expect(screen.getByTestId('primary-status').textContent).toBe('connected')

    act(() => {
      MockWebSocket.instances[0].emitClose()
    })

    expect(screen.getByTestId('primary-status').textContent).toBe('offline')

    act(() => {
      vi.advanceTimersByTime(1000)
    })

    expect(MockWebSocket.instances).toHaveLength(3)

    act(() => {
      MockWebSocket.instances[2].emitOpen()
    })

    expect(screen.getByTestId('primary-status').textContent).toBe('connected')
  })
})

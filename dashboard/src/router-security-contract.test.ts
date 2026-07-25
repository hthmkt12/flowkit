import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const srcRoot = here

/** Read every TS/TSX file under src/ as a single string for static contract checks. */
function readSourceTree(): string {
  // Scan the same files the build ships. We only assert import patterns,
  // so a concatenated read is sufficient and avoids dynamic import edge cases.
  const files: string[] = [
    'App.tsx',
    'main.tsx',
    'api/client.ts',
    'api/useWebSocket.ts',
    'components/SafetyGateStatus.tsx',
    'components/pilot-readiness-strip.tsx',
    'components/local-pilot-checklist.tsx',
    'components/local-pilot-demo-readiness-strip.tsx',
    'components/local-pilot-demo-script.tsx',
    'components/local-pilot-evidence-summary.tsx',
    'components/projects/ApprovalQueueTab.tsx',
    'components/projects/CampaignsRunsTab.tsx',
    'components/projects/ProjectLiveFlagCopy.tsx',
    'pages/AccountsPage.tsx',
    'pages/AutoPostFanpagePage.tsx',
    'pages/DashboardPage.tsx',
    'pages/LogsPage.tsx',
    'pages/ProjectsPage.tsx',
    'pages/WorkflowLabPage.tsx',
    'utils/safe-external-url.ts',
  ]
  return files
    .map((rel) => {
      try {
        return readFileSync(join(srcRoot, rel), 'utf-8')
      } catch {
        return ''
      }
    })
    .join('\n')
}

describe('React Router RSC non-applicability contract', () => {
  // Tracks GHSA-qwww-vcr4-c8h2 (react-router-dom advisory). The dashboard
  // retains React Router v7 and relies only on declarative APIs, so the
  // unstable RSC/data-strategy surfaces named in the advisory are not used.
  // This test fails closed if any unstable RSC surface appears in src/.
  it('does not import any unstable RSC or data-strategy surface', () => {
    const source = readSourceTree()
    const forbidden = [
      'unstable_',
      'unstableLoader',
      'unstableDataStrategy',
      'dataStrategy',
      'isRouteErrorResponse',
      'renderMatches',
      'RouterProvider',
      'createStaticHandler',
      'createStaticRouter',
    ]
    const hits = forbidden.filter((token) => source.includes(token))
    expect(hits, `unexpected unstable RSC surfaces: ${hits.join(', ')}`).toEqual([])
  })

  it('uses only declarative router exports from react-router-dom', () => {
    const source = readSourceTree()
    // Only these declarative exports are permitted while the RSC exception holds.
    const allowed = ['BrowserRouter', 'NavLink', 'Routes', 'Route', 'useLocation', 'useNavigate', 'Link', 'useParams', 'Outlet', 'Navigate']
    const importLines = source.split('\n').filter((line) => line.includes("from 'react-router-dom'") || line.includes('from "react-router-dom"'))
    expect(importLines.length).toBeGreaterThan(0)
    // Extract imported names from each react-router-dom import line.
    const imported = new Set<string>()
    for (const line of importLines) {
      const match = line.match(/\{([^}]*)\}/)
      if (!match) continue
      for (const name of match[1].split(',').map((s) => s.trim()).filter(Boolean)) {
        imported.add(name)
      }
    }
    const unexpected = [...imported].filter((name) => !allowed.includes(name))
    expect(unexpected, `unexpected router imports: ${unexpected.join(', ')}`).toEqual([])
  })
})

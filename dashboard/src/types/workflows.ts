export type WorkflowEvent = {
  captureId: string
  method: string
  host: string
  path: string
  status: number | null
  resourceType: string
  timingMs: number | null
  queryShape: string[]
}

export type WorkflowAnalysis = {
  captureId: string
  schemaVersion: number
  replayability: string
  readOnly: boolean
  executeAllowed: false
  eventCount: number
}

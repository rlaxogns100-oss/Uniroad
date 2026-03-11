import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const POSTHOG_HOST = process.env.POSTHOG_HOST || 'https://us.posthog.com'
const POSTHOG_PROJECT_ID = process.env.POSTHOG_PROJECT_ID
const POSTHOG_PERSONAL_API_KEY = process.env.POSTHOG_PERSONAL_API_KEY

if (!POSTHOG_PROJECT_ID || !POSTHOG_PERSONAL_API_KEY) {
  console.error('POSTHOG_PROJECT_ID, POSTHOG_PERSONAL_API_KEY 환경변수가 필요합니다.')
  process.exit(1)
}

const specPath = path.join(__dirname, 'posthog-dashboard-spec.json')
const spec = JSON.parse(await fs.readFile(specPath, 'utf8'))

async function request(method, apiPath, body) {
  const response = await fetch(`${POSTHOG_HOST}${apiPath}`, {
    method,
    headers: {
      Authorization: `Bearer ${POSTHOG_PERSONAL_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`${method} ${apiPath} 실패: ${response.status} ${text}`)
  }

  if (response.status === 204) return null
  return response.json()
}

const INTERNAL_FILTER = {
  key: 'is_internal',
  value: ['false'],
  operator: 'exact',
  type: 'event',
}

function mergeProperties(properties = []) {
  return [INTERNAL_FILTER, ...properties]
}

function buildTrendFilters(insight) {
  const events = insight.events
    ? insight.events.map((eventName, index) => ({
        id: eventName,
        name: eventName,
        order: index,
        type: 'events',
      }))
    : [
        {
          id: insight.event,
          name: insight.event,
          order: 0,
          type: 'events',
        },
      ]

  return {
    insight: 'TRENDS',
    display: insight.display || (insight.breakdown ? 'ActionsBarValue' : 'ActionsLineGraph'),
    events,
    breakdown: insight.breakdown || undefined,
    breakdown_type: insight.breakdown ? (insight.breakdown_type || 'event') : undefined,
    date_from: insight.date_from || '-30d',
    properties: mergeProperties(insight.properties),
  }
}

function buildFunnelFilters(insight) {
  return {
    insight: 'FUNNELS',
    layout: 'horizontal',
    events: insight.steps.map((eventName, index) => ({
      id: eventName,
      name: eventName,
      order: index,
      type: 'events',
    })),
    breakdown: insight.breakdown || undefined,
    breakdown_type: insight.breakdown ? (insight.breakdown_type || 'event') : undefined,
    date_from: insight.date_from || '-30d',
    properties: mergeProperties(insight.properties),
  }
}

function buildRetentionFilters(insight) {
  return {
    insight: 'RETENTION',
    target_entity: {
      id: insight.event,
      name: insight.event,
      type: 'events',
    },
    returning_entity: {
      id: insight.event,
      name: insight.event,
      type: 'events',
    },
    date_from: insight.date_from || '-30d',
    properties: mergeProperties(insight.properties),
  }
}

function buildPathsFilters(insight) {
  return {
    insight: 'PATHS',
    path_type: insight.path_type || 'custom_event',
    start_point: insight.start_point || undefined,
    end_point: insight.end_point || undefined,
    step_limit: insight.step_limit || 5,
    date_from: insight.date_from || '-30d',
    properties: mergeProperties(insight.properties),
  }
}

function buildInsightPayload(insight) {
  let filters
  if (insight.type === 'funnel') {
    filters = buildFunnelFilters(insight)
  } else if (insight.type === 'retention') {
    filters = buildRetentionFilters(insight)
  } else if (insight.type === 'paths') {
    filters = buildPathsFilters(insight)
  } else {
    filters = buildTrendFilters(insight)
  }

  return {
    name: insight.name,
    derived_name: insight.name,
    filters,
  }
}

async function ensureDashboard() {
  const existing = await request(
    'GET',
    `/api/projects/${POSTHOG_PROJECT_ID}/dashboards/?search=${encodeURIComponent(spec.dashboard.name)}`
  )

  const dashboard = Array.isArray(existing?.results)
    ? existing.results.find((item) => item.name === spec.dashboard.name)
    : null

  if (dashboard) return dashboard

  return request('POST', `/api/projects/${POSTHOG_PROJECT_ID}/dashboards/`, {
    name: spec.dashboard.name,
    description: spec.dashboard.description,
  })
}

async function createInsight(insight) {
  const payload = buildInsightPayload(insight)
  return request('POST', `/api/projects/${POSTHOG_PROJECT_ID}/insights/`, payload)
}

async function updateInsight(insightId, insight) {
  const payload = buildInsightPayload(insight)
  return request('PATCH', `/api/projects/${POSTHOG_PROJECT_ID}/insights/${insightId}/`, payload)
}

async function findInsightByName(name) {
  const existing = await request(
    'GET',
    `/api/projects/${POSTHOG_PROJECT_ID}/insights/?search=${encodeURIComponent(name)}&limit=20`
  )
  return Array.isArray(existing?.results)
    ? existing.results.find((item) => item.name === name && !item.deleted)
    : null
}

async function attachInsightToDashboard(insightId, dashboardId) {
  return request('PATCH', `/api/projects/${POSTHOG_PROJECT_ID}/insights/${insightId}/`, {
    dashboards: [dashboardId],
  })
}

async function main() {
  const dashboard = await ensureDashboard()
  console.log(`Dashboard: ${dashboard.name} (#${dashboard.id})`)

  for (const insight of spec.insights) {
    const existing = await findInsightByName(insight.name)
    const saved = existing
      ? await updateInsight(existing.id, insight)
      : await createInsight(insight)

    console.log(`Insight ${existing ? 'updated' : 'created'}: ${saved.name} (#${saved.id})`)
    await attachInsightToDashboard(saved.id, dashboard.id)
    console.log(`Insight attached: ${saved.name} -> dashboard #${dashboard.id}`)
  }

  console.log('PostHog dashboard setup finished.')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

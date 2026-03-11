import process from 'node:process'

const POSTHOG_HOST = process.env.POSTHOG_HOST || 'https://us.posthog.com'
const PROJECT_ID = process.env.POSTHOG_PROJECT_ID || '335960'
const API_KEY = process.env.POSTHOG_PERSONAL_API_KEY

if (!API_KEY) {
  console.error('POSTHOG_PERSONAL_API_KEY 환경변수가 필요합니다.')
  process.exit(1)
}

const DASHBOARD_ID = 1348248

const INTERNAL_FILTER = {
  key: 'is_internal',
  value: ['false'],
  operator: 'exact',
  type: 'event',
}

async function request(method, apiPath, body) {
  const response = await fetch(`${POSTHOG_HOST}${apiPath}`, {
    method,
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`${method} ${apiPath} failed: ${response.status} ${text}`)
  }

  if (response.status === 204) return null
  return response.json()
}

async function createInsight(payload) {
  const created = await request(
    'POST',
    `/api/projects/${PROJECT_ID}/insights/`,
    payload
  )
  console.log(`  Created: ${created.name} (#${created.id})`)
  await request(
    'PATCH',
    `/api/projects/${PROJECT_ID}/insights/${created.id}/`,
    { dashboards: [DASHBOARD_ID] }
  )
  console.log(`  Attached to dashboard #${DASHBOARD_ID}`)
  return created
}

async function patchInsight(insightId, payload) {
  const updated = await request(
    'PATCH',
    `/api/projects/${PROJECT_ID}/insights/${insightId}/`,
    payload
  )
  console.log(`  Patched: ${updated.name} (#${updated.id})`)
  return updated
}

async function findInsightByName(name) {
  const result = await request(
    'GET',
    `/api/projects/${PROJECT_ID}/insights/?search=${encodeURIComponent(name)}&limit=10`
  )
  if (result?.results) {
    return result.results.find((i) => i.name === name && !i.deleted)
  }
  return null
}

async function main() {
  console.log('\n=== 1. User Paths (첫 행동 경로) ===')
  await createInsight({
    name: 'First Action Path',
    filters: {
      insight: 'PATHS',
      path_type: 'custom_event',
      start_point: 'page_view',
      step_limit: 5,
      date_from: '-14d',
      properties: [INTERNAL_FILTER],
    },
  })

  console.log('\n=== 2. Active Traffic (활성 유입 비율) ===')
  await createInsight({
    name: 'Active Traffic Ratio',
    filters: {
      insight: 'FUNNELS',
      layout: 'horizontal',
      funnel_viz_type: 'steps',
      date_from: '-14d',
      events: [
        { id: 'page_view', name: 'page_view', order: 0, type: 'events' },
        { id: 'chat_message_sent', name: 'chat_message_sent', order: 1, type: 'events' },
      ],
      exclusions: [],
      properties: [INTERNAL_FILTER],
    },
  })

  console.log('\n=== 3. Reverse Path to Signup (회원가입 직전 행동) ===')
  await createInsight({
    name: 'Reverse Path to Signup',
    filters: {
      insight: 'PATHS',
      path_type: 'custom_event',
      end_point: 'signup_completed',
      step_limit: 5,
      date_from: '-30d',
      properties: [INTERNAL_FILTER],
    },
  })

  console.log('\n=== 4. Pie Charts (유입 경로/기기 비율) ===')

  const trafficSource = await findInsightByName('Traffic Source Mix')
  if (trafficSource) {
    console.log(`  Found existing "Traffic Source Mix" (#${trafficSource.id}), patching to Pie...`)
    const filters = { ...trafficSource.filters, display: 'ActionsPie' }
    await patchInsight(trafficSource.id, { filters })
  } else {
    console.log('  "Traffic Source Mix" not found, creating new Pie...')
    await createInsight({
      name: 'Traffic Source Mix',
      filters: {
        insight: 'TRENDS',
        display: 'ActionsPie',
        date_from: '-14d',
        events: [
          { id: 'page_view', name: 'page_view', order: 0, type: 'events' },
        ],
        breakdown: 'utm_source',
        breakdown_type: 'event',
        properties: [INTERNAL_FILTER],
      },
    })
  }

  const deviceMix = await findInsightByName('Device Mix')
  if (deviceMix) {
    console.log(`  Found existing "Device Mix" (#${deviceMix.id}), patching to Pie...`)
    const filters = { ...deviceMix.filters, display: 'ActionsPie' }
    await patchInsight(deviceMix.id, { filters })
  } else {
    console.log('  "Device Mix" not found, creating new Pie...')
    await createInsight({
      name: 'Device Mix',
      filters: {
        insight: 'TRENDS',
        display: 'ActionsPie',
        date_from: '-14d',
        events: [
          { id: 'page_view', name: 'page_view', order: 0, type: 'events' },
        ],
        breakdown: 'device_type',
        breakdown_type: 'event',
        properties: [INTERNAL_FILTER],
      },
    })
  }

  console.log('\n=== Done! ===')
  console.log(`Dashboard: ${POSTHOG_HOST}/project/${PROJECT_ID}/dashboard/${DASHBOARD_ID}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

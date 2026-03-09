// =============================================================================
// api/trigger-job.js — Vercel Edge Function
// Triggers a RunPod serverless job for a given room.
//
// Expected request body: { roomId: "<uuid>" }
// Returns:               { ok: true, jobId: "<runpod-job-id>" }
//
// Uses raw fetch (no npm dependencies) for Edge Function compatibility.
// =============================================================================

export const config = { runtime: 'edge' }

const SB_URL = () => process.env.SUPABASE_URL
const SB_KEY = () => process.env.SUPABASE_SERVICE_KEY

/** Helper: Supabase REST API fetch with service-role auth */
async function sbFetch(path, options = {}) {
  const resp = await fetch(`${SB_URL()}/rest/v1/${path}`, {
    ...options,
    headers: {
      'apikey': SB_KEY(),
      'Authorization': `Bearer ${SB_KEY()}`,
      'Content-Type': 'application/json',
      'Prefer': options.prefer || '',
      ...options.headers,
    },
  })
  return resp
}

export default async function handler(req) {
  if (req.method !== 'POST') {
    return Response.json({ error: 'Method not allowed' }, { status: 405 })
  }

  let roomId
  try {
    const body = await req.json()
    roomId = body.roomId
  } catch {
    return Response.json({ error: 'Invalid JSON body' }, { status: 400 })
  }

  if (!roomId) {
    return Response.json({ error: 'roomId is required' }, { status: 400 })
  }

  // 1. Fetch room details
  const selectResp = await sbFetch(
    `tour_rooms?id=eq.${roomId}&select=id,tour_id,agent_id,mode,style,prompt,input_folder,status`,
    { prefer: 'return=representation' }
  )

  if (!selectResp.ok) {
    const err = await selectResp.text()
    console.error('[trigger-job] Supabase select error:', err)
    return Response.json({ error: 'Room not found' }, { status: 404 })
  }

  const rows = await selectResp.json()
  if (!rows || rows.length === 0) {
    console.error('[trigger-job] Room not found:', roomId)
    return Response.json({ error: 'Room not found' }, { status: 404 })
  }
  const room = rows[0]

  // 2. Guard: don't re-trigger jobs that are already running
  if (room.status === 'processing' || room.status === 'done') {
    return Response.json({ error: `Room already in status: ${room.status}` }, { status: 409 })
  }

  // 3. Mark room as processing before dispatching
  const updateResp = await sbFetch(
    `tour_rooms?id=eq.${roomId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ status: 'processing' }),
    }
  )

  if (!updateResp.ok) {
    const err = await updateResp.text()
    console.error('[trigger-job] Failed to update status:', err)
    return Response.json({ error: 'Failed to update room status' }, { status: 500 })
  }

  // 4. Dispatch RunPod serverless job
  let runpodResponse
  try {
    runpodResponse = await fetch(`${process.env.RUNPOD_ENDPOINT}/run`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        input: {
          room_id:      room.id,
          tour_id:      room.tour_id,
          agent_id:     room.agent_id,
          mode:         room.mode,
          style:        room.style,
          prompt:       room.prompt,
          input_folder: room.input_folder
        }
      })
    })
  } catch (fetchError) {
    console.error('[trigger-job] RunPod fetch failed:', fetchError)
    // Revert status so user can retry
    await sbFetch(`tour_rooms?id=eq.${roomId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'pending', error_msg: 'RunPod unreachable' }),
    })
    return Response.json({ error: 'Failed to reach RunPod endpoint' }, { status: 502 })
  }

  if (!runpodResponse.ok) {
    const errText = await runpodResponse.text()
    console.error('[trigger-job] RunPod error:', runpodResponse.status, errText)
    await sbFetch(`tour_rooms?id=eq.${roomId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'pending', error_msg: `RunPod error ${runpodResponse.status}` }),
    })
    return Response.json({ error: 'RunPod rejected job' }, { status: 502 })
  }

  const runpodData = await runpodResponse.json()
  console.log('[trigger-job] Job dispatched:', roomId, 'jobId:', runpodData.id)

  return Response.json({ ok: true, jobId: runpodData.id })
}

// api/analytics.js — Vercel Edge Function
// Increments the view counter for a public tour via Supabase RPC.
// No auth required. Uses raw fetch (no npm dependencies).

export const config = { runtime: 'edge' }

export default async function handler(req) {
  if (req.method !== 'POST') {
    return Response.json({ error: 'Method not allowed' }, { status: 405 })
  }

  let tourId
  try {
    const body = await req.json()
    tourId = body.tourId
  } catch {
    return Response.json({ error: 'Invalid JSON body' }, { status: 400 })
  }

  if (!tourId) {
    return Response.json({ error: 'tourId is required' }, { status: 400 })
  }

  const resp = await fetch(
    `${process.env.SUPABASE_URL}/rest/v1/rpc/increment_view_count`,
    {
      method: 'POST',
      headers: {
        'apikey': process.env.SUPABASE_ANON_KEY,
        'Authorization': `Bearer ${process.env.SUPABASE_ANON_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ tour_id: tourId }),
    }
  )

  if (!resp.ok) {
    const err = await resp.text()
    console.error('[analytics] RPC error:', err)
    return Response.json({ ok: false }, { status: 500 })
  }

  return Response.json({ ok: true })
}

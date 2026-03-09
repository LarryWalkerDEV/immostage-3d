// =============================================================================
// api/remove-watermark.js — Vercel Edge Function
// Stub for future payment-gated watermark removal.
//
// When payment integration is implemented:
//   1. Verify Stripe payment / subscription status
//   2. Update agents.watermark = false AND agents.plan = 'starter'
//   3. Propagate watermark: false to all active tours
//
// Expected request body: { tourId?: "<uuid>" }   (optional: remove from one tour)
// Returns:               { ok: false, message: "Coming soon" }
// =============================================================================

export const config = { runtime: 'edge' }

export default async function handler(req) {
  if (req.method !== 'POST') {
    return Response.json({ error: 'Method not allowed' }, { status: 405 })
  }

  // TODO: integrate Stripe checkout / webhook
  // TODO: verify payment before updating DB
  return Response.json(
    {
      ok: false,
      message: 'Coming soon — upgrade to a paid plan to remove the watermark.'
    },
    { status: 200 }
  )
}

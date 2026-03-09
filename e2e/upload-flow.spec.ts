import { test, expect } from '@playwright/test'
import * as path from 'path'
import * as fs from 'fs'

const BASE = process.env.BASE_URL || 'https://immostage-3d.vercel.app'
const TEST_EMAIL = 'e2e-test@immoapp.test'
const TEST_PASSWORD = 'TestPassword123!'
const IMAGES_DIR = 'C:/Users/eugen/.cursor/projects/immoapp/docs/test images 3d'

// Supabase REST helper for verification
const SB_URL = 'https://psrbfzdsgpcuqokyqcso.supabase.co'
const SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBzcmJmemRzZ3BjdXFva3lxY3NvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NzQ1MDUxMiwiZXhwIjoyMDgzMDI2NTEyfQ.deHAi9pmKG5QQ74RQnqohp4kQkVStH3JWlZGfCIBLe8'

async function sbQuery(table: string, params = '') {
  const resp = await fetch(`${SB_URL}/rest/v1/${table}?${params}`, {
    headers: {
      'apikey': SB_KEY,
      'Authorization': `Bearer ${SB_KEY}`,
    },
  })
  return resp.json()
}

async function sbStorageList(prefix: string) {
  const resp = await fetch(`${SB_URL}/storage/v1/object/list/scans`, {
    method: 'POST',
    headers: {
      'apikey': SB_KEY,
      'Authorization': `Bearer ${SB_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ prefix, limit: 100 }),
  })
  return resp.json()
}

test.describe('ImmoStage 3D — Upload Flow', () => {

  test('login, create tour, upload images, verify in DB', async ({ page }) => {
    // 1. Navigate and login
    await page.goto(BASE + '/index.html')
    await expect(page.locator('#btn-login')).toBeVisible({ timeout: 15000 })

    await page.fill('#login-email', TEST_EMAIL)
    await page.fill('#login-password', TEST_PASSWORD)
    await page.click('#btn-login')

    // Wait for home screen
    await expect(page.locator('#screen-home.active')).toBeVisible({ timeout: 10000 })

    // 2. Start new scan
    await page.click('#btn-new-scan')
    await expect(page.locator('#screen-setup.active')).toBeVisible({ timeout: 5000 })

    // Fill tour details
    await page.fill('#tour-title', 'E2E Test Tour - Dachgeschoss')
    await page.fill('#tour-address', 'Teststraße 42, 10115 Berlin')
    await page.fill('#room-name-new', 'Wohnzimmer')

    // 3. Start capture — but we need to inject images instead of using camera
    // The capture screen requires camera permissions. Instead, we'll inject
    // test photos directly into the app state via JavaScript.
    const imageFiles = fs.readdirSync(IMAGES_DIR)
      .filter(f => f.endsWith('.jpg'))
      .sort()
      .slice(0, 12)

    // Inject photos into app state (bypass camera capture)
    for (let i = 0; i < imageFiles.length; i++) {
      const imgPath = path.join(IMAGES_DIR, imageFiles[i])
      const imgBuffer = fs.readFileSync(imgPath)
      const base64 = imgBuffer.toString('base64')

      await page.evaluate(({ b64, idx }) => {
        const binary = atob(b64)
        const bytes = new Uint8Array(binary.length)
        for (let j = 0; j < binary.length; j++) bytes[j] = binary.charCodeAt(j)
        const blob = new Blob([bytes], { type: 'image/jpeg' })

        // Access app state
        const state = (window as any).State
        if (!state.capturedPhotos) state.capturedPhotos = []
        state.capturedPhotos.push({
          blob,
          imu: { yaw: (idx * 30) % 360, pitch: 90 }
        })

        // Mark guide point as captured
        if (state.guidePoints && state.guidePoints[idx]) {
          state.guidePoints[idx].captured = true
        }
      }, { b64: base64, idx: i })
    }

    // Navigate to review screen
    await page.evaluate(() => {
      const state = (window as any).State
      ;(window as any).buildReviewGrid()
      ;(window as any).showScreen('review')
    })

    await expect(page.locator('#screen-review.active')).toBeVisible({ timeout: 5000 })

    // Verify photo count displayed
    const reviewCount = await page.locator('#review-count').textContent()
    expect(parseInt(reviewCount || '0')).toBeGreaterThanOrEqual(8)

    // 4. Set tour details + mode in state
    await page.evaluate(() => {
      const state = (window as any).State
      state.tourTitle = 'E2E Test Tour - Dachgeschoss'
      state.tourAddress = 'Teststraße 42, 10115 Berlin'
      state.roomName = 'Wohnzimmer'
      state.selectedMode = 'real'
      state.selectedStyle = 'modern'
    })

    // Click submit (the function handles tour creation + upload)
    await page.evaluate(() => {
      ;(window as any).submitJob()
    })

    // Wait for processing screen
    await expect(page.locator('#screen-processing.active')).toBeVisible({ timeout: 10000 })

    // 5. Wait for uploads to finish (check upload step)
    // The upload step should change from 'active' to 'done'
    await page.waitForTimeout(10000) // Give time for uploads

    // 6. Verify data reached Supabase
    const tours = await sbQuery('tours', 'order=created_at.desc&limit=1')
    expect(tours.length).toBeGreaterThan(0)
    expect(tours[0].title).toBe('E2E Test Tour - Dachgeschoss')
    expect(tours[0].address).toBe('Teststraße 42, 10115 Berlin')

    const tourId = tours[0].id
    console.log('Tour created:', tourId)

    const rooms = await sbQuery('tour_rooms', `tour_id=eq.${tourId}&limit=1`)
    expect(rooms.length).toBeGreaterThan(0)
    expect(rooms[0].name).toBe('Wohnzimmer')
    expect(rooms[0].mode).toBe('real')

    const roomId = rooms[0].id
    console.log('Room created:', roomId, 'status:', rooms[0].status)

    // Check storage for uploaded images
    const files = await sbStorageList(`scans/${roomId}/input`)
    console.log('Uploaded files:', files.length)
    expect(files.length).toBeGreaterThanOrEqual(8)

    // 7. Screenshot for evidence
    await page.screenshot({ path: 'verification/3d-upload-flow.png', fullPage: true })
  })

  test('verify tour shows in dashboard', async ({ page }) => {
    await page.goto(BASE + '/dashboard.html')
    await expect(page.locator('input[type="email"]')).toBeVisible({ timeout: 15000 })

    await page.fill('input[type="email"]', TEST_EMAIL)
    await page.fill('input[type="password"]', TEST_PASSWORD)
    await page.click('text=Anmelden')

    // Wait for dashboard to load tours
    await page.waitForTimeout(5000)

    // Check if tour card appears
    const tourCard = page.locator('text=E2E Test Tour - Dachgeschoss')
    await expect(tourCard.first()).toBeVisible({ timeout: 10000 })

    await page.screenshot({ path: 'verification/3d-dashboard.png', fullPage: true })
  })
})

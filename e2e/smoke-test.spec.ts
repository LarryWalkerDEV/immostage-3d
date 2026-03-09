import { test, expect } from '@playwright/test'

const BASE = process.env.BASE_URL || 'https://immostage-3d.vercel.app'

test.describe('ImmoStage 3D — Smoke Tests', () => {

  test('index.html loads and shows login screen', async ({ page }) => {
    await page.goto(BASE + '/index.html')
    await expect(page).toHaveTitle(/ImmoStage 3D/)
    // Login screen should be visible (wait for Supabase CDN to load)
    await expect(page.locator('#btn-login')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('#login-email')).toBeVisible()
    await expect(page.locator('#login-password')).toBeVisible()
  })

  test('index.html has Demo mode button', async ({ page }) => {
    await page.goto(BASE + '/index.html')
    await expect(page.locator('#btn-demo')).toBeVisible({ timeout: 15000 })
  })

  test('tour.html loads and shows error for missing tour ID', async ({ page }) => {
    await page.goto(BASE + '/tour.html')
    // Should show error state (no tour ID in URL)
    await expect(page.locator('text=/nicht gefunden|Fehler|error/i').first()).toBeVisible({ timeout: 5000 })
  })

  test('dashboard.html loads and shows login prompt', async ({ page }) => {
    await page.goto(BASE + '/dashboard.html')
    await expect(page).toHaveTitle(/ImmoStage|Dashboard/)
    // Should show login form since not authenticated
    await expect(page.locator('input[type="email"]')).toBeVisible({ timeout: 15000 })
  })

  test('manifest.json is valid', async ({ page }) => {
    const resp = await page.goto(BASE + '/manifest.json')
    expect(resp?.status()).toBe(200)
    const json = await resp?.json()
    expect(json.name).toBe('ImmoStage 3D')
    expect(json.display).toBe('standalone')
    expect(json.icons.length).toBeGreaterThan(0)
  })

  test('sw.js service worker is accessible', async ({ page }) => {
    const resp = await page.goto(BASE + '/sw.js')
    expect(resp?.status()).toBe(200)
    const text = await resp?.text()
    expect(text).toContain('immostage')
  })

  test('watermark badge.svg loads', async ({ page }) => {
    const resp = await page.goto(BASE + '/watermark/badge.svg')
    expect(resp?.status()).toBe(200)
    const text = await resp?.text()
    expect(text).toContain('svg')
  })

  test('supabase-client.js loads', async ({ page }) => {
    const resp = await page.goto(BASE + '/supabase-client.js')
    expect(resp?.status()).toBe(200)
    const text = await resp?.text()
    expect(text).toContain('supabase')
  })

  test('joystick.js loads and exports createJoystick', async ({ page }) => {
    const resp = await page.goto(BASE + '/joystick.js')
    expect(resp?.status()).toBe(200)
    const text = await resp?.text()
    expect(text).toContain('createJoystick')
  })

  test('index.html demo mode starts capture flow', async ({ page }) => {
    await page.goto(BASE + '/index.html')
    // Wait for demo button to be visible
    const demoBtn = page.locator('#btn-demo')
    await expect(demoBtn).toBeVisible({ timeout: 15000 })
    await demoBtn.click()
    // Should navigate past login — home screen should become active
    await expect(page.locator('#screen-home.active')).toBeVisible({ timeout: 10000 })
  })
})

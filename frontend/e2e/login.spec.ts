import { expect, test } from '@playwright/test'

const username = process.env.E2E_USERNAME ?? ''
const password = process.env.E2E_PASSWORD ?? ''

test('credenciales incorrectas muestran un mensaje genérico', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Usuario').fill('no-existe')
  await page.getByLabel('Contraseña', { exact: true }).fill('incorrecta-123')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page.getByText('No se pudo iniciar sesión')).toBeVisible()
})

test('inicio de sesión y dashboard', async ({ page }) => {
  test.skip(!username || !password, 'Defina E2E_USERNAME y E2E_PASSWORD')
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/)
  await page.getByLabel('Usuario').fill(username)
  await page.getByLabel('Contraseña', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page.getByRole('heading', { name: 'El agua, en perspectiva.' })).toBeVisible()
  await expect(page.getByText('Agua captada hoy')).toBeVisible()
  await page.screenshot({ path: process.env.E2E_SCREENSHOT ?? 'test-results/dashboard.png', fullPage: true })
})

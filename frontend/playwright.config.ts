import { defineConfig, devices } from '@playwright/test'

// Requiere la API local en ejecución y un usuario de prueba (E2E_USERNAME / E2E_PASSWORD).
export default defineConfig({
  testDir: './e2e',
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173', trace: 'on-first-retry' },
  projects: [
    {
      name: 'chromium',
      // CHROMIUM_PATH permite usar el navegador del sistema en equipos sin conexión.
      use: { ...devices['Desktop Chrome'], launchOptions: { executablePath: process.env.CHROMIUM_PATH || undefined } },
    },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : { command: 'npm run dev', url: 'http://localhost:5173', reuseExistingServer: true },
})

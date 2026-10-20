import '@testing-library/jest-dom/vitest'

// jsdom no implementa ResizeObserver, que usan algunos componentes de Radix (shadcn/ui).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

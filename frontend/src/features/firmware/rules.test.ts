import { imageError, MAX_IMAGE_BYTES } from '@/features/firmware/rules'

const file = (name: string, size: number) => new File([new Uint8Array(size)], name)

test('valida el archivo de firmware antes de cargarlo', () => {
  expect(imageError(null)).toMatch(/Seleccione/)
  expect(imageError(file('firmware.elf', 10))).toMatch(/\.bin/)
  expect(imageError(file('firmware.bin', MAX_IMAGE_BYTES + 1))).toMatch(/máximo/)
  expect(imageError(file('firmware.bin', MAX_IMAGE_BYTES))).toBeNull()
})

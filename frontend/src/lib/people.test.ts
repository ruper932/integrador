import { ageOn, birthDateError, earliestGraduationYear, latestAdultBirthDate } from '@/lib/people'

test('edad en años cumplidos', () => {
  expect(ageOn('2008-10-16', '2026-10-15')).toBe(17)
  expect(ageOn('2008-10-15', '2026-10-15')).toBe(18)
})

test('validación de la fecha de nacimiento', () => {
  expect(birthDateError('2008-10-15', '2026-10-15')).toBeNull()
  expect(birthDateError('2008-10-16', '2026-10-15')).toMatch(/mayor de edad/)
  expect(birthDateError('2030-01-01', '2026-10-15')).toMatch(/futura/)
  expect(birthDateError('', '2026-10-15')).toMatch(/Indique/)
  expect(latestAdultBirthDate('2026-10-15')).toBe('2008-10-15')
})

test('primer año de egreso posible', () => {
  expect(earliestGraduationYear('2008-10-15', 21)).toBe(2029)
})

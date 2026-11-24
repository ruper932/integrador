import { configCommands, type StationSettings } from '@/features/firmware/flasher'

const settings: StationSettings = {
  ssid: 'Red CEA',
  wifiPassword: 'clave con espacios',
  apiUrl: 'http://192.168.1.10/api/v1/iot/measurements/batch',
  ntp: '192.168.1.10',
  deviceCode: 'esp32-01',
  apiKey: 'dk_secreta',
  sampleSeconds: 60,
}

test('arma los comandos del firmware y termina guardando', () => {
  expect(configCommands(settings)).toEqual([
    'set ssid Red CEA',
    'set wifi_pass clave con espacios',
    'set api_url http://192.168.1.10/api/v1/iot/measurements/batch',
    'set device_id esp32-01',
    'set device_key dk_secreta',
    'set ntp 192.168.1.10',
    'set sample_s 60',
    'save',
  ])
})

test('una red abierta no envía contraseña y un salto de línea se rechaza', () => {
  expect(configCommands({ ...settings, wifiPassword: '' })).not.toContainEqual(expect.stringContaining('wifi_pass'))
  expect(() => configCommands({ ...settings, ssid: 'red\nsave' })).toThrow(/saltos de línea/)
})

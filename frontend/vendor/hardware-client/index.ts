/** OqlOS hardware REST paths shared by connect-scenario UI and backends. */

export const OQLOS_HARDWARE_V1 = '/api/v1/hardware';
export const CONNECT_HARDWARE_V3 = '/api/v3/hardware';

export const ARTIFICIAL_LUNG_IDS = ['artificial-lung', 'lung', 'lung-main'] as const;

export type ArtificialLungId = (typeof ARTIFICIAL_LUNG_IDS)[number];

export const PERIPHERAL_STATUS_COMMANDS: Record<string, string> = {
  'modbus-io': 'health',
  'motor-dri0050': 'status',
  'motor-tic249': 'status',
  'artificial-lung': 'status',
  lung: 'status',
  'lung-main': 'status',
  rtc: 'status',
  'modbus-adc': 'read_sensor',
  piadc: 'read_sensor',
};

export { CONNECT_HARDWARE_PATHS, connectCqrsEventsPath } from './paths.js';
export { connectPeripheralStatusPath, connectDiagnosticCommandPath } from './paths.js';

export function oqlosArtificialLungCommandPath(): string {
  return `${OQLOS_HARDWARE_V1}/artificial-lung/command`;
}

export function oqlosArtificialLungStatusPath(): string {
  return `${OQLOS_HARDWARE_V1}/artificial-lung/status`;
}

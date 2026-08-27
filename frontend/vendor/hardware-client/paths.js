/** Connect-scenario v3 hardware API paths (proxy to OqlOS). */

import { CONNECT_HARDWARE_V3 } from './index.js';

export const CONNECT_HARDWARE_PATHS = {
  health: `${CONNECT_HARDWARE_V3}/health`,
  identify: `${CONNECT_HARDWARE_V3}/identify`,
  proxyInfo: `${CONNECT_HARDWARE_V3}/proxy-info`,
  diagnosticCommand: `${CONNECT_HARDWARE_V3}/diagnostic-command`,
  cqrsCommand: `${CONNECT_HARDWARE_V3}/cqrs/command`,
  cqrsEvents: `${CONNECT_HARDWARE_V3}/cqrs/events`,
  cqrsEventsClear: `${CONNECT_HARDWARE_V3}/cqrs/events/clear`,
  scannerStatus: `${CONNECT_HARDWARE_V3}/scanner/status`,
  scannerLast: `${CONNECT_HARDWARE_V3}/scanner/last`,
  scannerIngest: `${CONNECT_HARDWARE_V3}/scanner/ingest`,
  diagnosis: `${CONNECT_HARDWARE_V3}/diagnosis`,
  diagnosisRepair: `${CONNECT_HARDWARE_V3}/diagnosis/repair`,
};

export function connectPeripheralStatusPath(peripheralId) {
  return `${CONNECT_HARDWARE_V3}/peripheral-status/${encodeURIComponent(peripheralId)}`;
}

export function connectDiagnosticCommandPath() {
  return CONNECT_HARDWARE_PATHS.diagnosticCommand;
}

export function connectCqrsEventsPath(limit = 50) {
  const q = Number.isFinite(limit) ? Math.max(1, Math.min(500, Number(limit))) : 50;
  return `${CONNECT_HARDWARE_PATHS.cqrsEvents}?limit=${q}`;
}

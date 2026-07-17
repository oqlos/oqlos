/** Connect-scenario v3 hardware API paths (proxy to OqlOS). */

import { CONNECT_HARDWARE_V3 } from './index.js';

export const CONNECT_HARDWARE_PATHS = {
  health: `${CONNECT_HARDWARE_V3}/health`,
  identify: `${CONNECT_HARDWARE_V3}/identify`,
  proxyInfo: `${CONNECT_HARDWARE_V3}/proxy-info`,
  diagnosticCommand: `${CONNECT_HARDWARE_V3}/diagnostic-command`,
  runtimePython: `${CONNECT_HARDWARE_V3}/runtime-python`,
  runtimePythonResolveFunc: `${CONNECT_HARDWARE_V3}/runtime-python/resolve-func`,
  mapping: `${CONNECT_HARDWARE_V3}/mapping`,
  mappingSchema: `${CONNECT_HARDWARE_V3}/mapping/schema`,
  mappingAccessPolicy: `${CONNECT_HARDWARE_V3}/mapping/access-policy`,
  mappingImport: `${CONNECT_HARDWARE_V3}/mapping/import`,
  mappingExport: `${CONNECT_HARDWARE_V3}/mapping/export`,
  mappingReset: `${CONNECT_HARDWARE_V3}/mapping/reset`,
  oqlMappedExec: `${CONNECT_HARDWARE_V3}/oql-mapped-exec`,
  cqrsCommand: `${CONNECT_HARDWARE_V3}/cqrs/command`,
  cqrsEvents: `${CONNECT_HARDWARE_V3}/cqrs/events`,
  cqrsEventsClear: `${CONNECT_HARDWARE_V3}/cqrs/events/clear`,
  scannerStatus: `${CONNECT_HARDWARE_V3}/scanner/status`,
  scannerLast: `${CONNECT_HARDWARE_V3}/scanner/last`,
  scannerIngest: `${CONNECT_HARDWARE_V3}/scanner/ingest`,
  diagnosis: `${CONNECT_HARDWARE_V3}/diagnosis`,
  diagnosisRepair: `${CONNECT_HARDWARE_V3}/diagnosis/repair`,
} as const;

export function connectPeripheralStatusPath(peripheralId: string): string {
  return `${CONNECT_HARDWARE_V3}/peripheral-status/${encodeURIComponent(peripheralId)}`;
}

export function connectDiagnosticCommandPath(): string {
  return CONNECT_HARDWARE_PATHS.diagnosticCommand;
}

/** Role-scoped MAP layer patch: system | administrator | operator */
export function connectMappingLayerPath(persona: string): string {
  const layer = encodeURIComponent(String(persona || "operator").trim().toLowerCase() || "operator");
  return `${CONNECT_HARDWARE_V3}/mapping/layer/${layer}`;
}

export function connectCqrsEventsPath(limit = 50): string {
  const q = Number.isFinite(limit) ? Math.max(1, Math.min(500, Number(limit))) : 50;
  return `${CONNECT_HARDWARE_PATHS.cqrsEvents}?limit=${q}`;
}

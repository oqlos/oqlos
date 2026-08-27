export const M5_POLL_ONLINE_MS = 1500;
export const M5_POLL_OFFLINE_INITIAL_MS = 10000;
export const M5_POLL_OFFLINE_MAX_MS = 30000;

export function nextM5OfflinePollDelay(currentDelayMs) {
  if (!Number.isFinite(currentDelayMs) || currentDelayMs < M5_POLL_OFFLINE_INITIAL_MS) {
    return M5_POLL_OFFLINE_INITIAL_MS;
  }
  return Math.min(currentDelayMs * 2, M5_POLL_OFFLINE_MAX_MS);
}

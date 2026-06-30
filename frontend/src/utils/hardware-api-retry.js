import { formatHardwareApiError } from "../api/hardware-api-errors.js";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const RETRYABLE_HTTP_STATUSES = new Set([502, 503, 504]);

export async function runApiWithRetry(
  label,
  action,
  { log, t, allowRetry = true, retryDelaysMs = [900, 1600], fallbackMessage = "Blad wywolania API." } = {},
) {
  let attempt = 0;
  while (true) {
    try {
      return await action();
    } catch (err) {
      const message = formatHardwareApiError(err, fallbackMessage);
      const retryable = allowRetry && RETRYABLE_HTTP_STATUSES.has(Number(err?.status));
      if (!retryable || attempt >= retryDelaysMs.length) {
        if (!allowRetry && Number(err?.status) === 502 && typeof t === "function") {
          const gatewayErr = new Error(`${message} (${t("hardwareRestart.probeNoQuickRetry")})`);
          gatewayErr.status = err?.status;
          gatewayErr.body = err?.body;
          throw gatewayErr;
        }
        throw err;
      }
      const waitMs = retryDelaysMs[attempt];
      if (typeof log === "function") {
        log(`${label}: OqlOS chwilowo niedostepny (${message}), ponawiam za ${waitMs} ms...`);
      }
      await sleep(waitMs);
      attempt += 1;
    }
  }
}

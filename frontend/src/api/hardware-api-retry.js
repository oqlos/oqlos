/**
 * Retry wrapper for transient hardware/gateway HTTP failures (502/503/504).
 *
 * SSOT — import from `@semcod/frontend-services/hardware-api-retry.js`.
 */
import { formatHardwareApiError } from "./hardware-api-errors.js";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const RETRYABLE_HTTP_STATUSES = new Set([502, 503, 504]);

/**
 * @param {string} label  short name for log lines
 * @param {() => Promise<any>} action
 * @param {object} [opts]
 * @param {(msg: string) => void} [opts.log]
 * @param {(key: string) => string} [opts.t]  i18n; used when allowRetry=false on 502
 * @param {boolean} [opts.allowRetry=true]
 * @param {number[]} [opts.retryDelaysMs]
 * @param {string} [opts.fallbackMessage]
 * @param {string} [opts.unavailableHint]  default log fragment before wait
 * @param {string} [opts.noRetryI18nKey]  t() key when 502 and allowRetry=false
 */
export async function runApiWithRetry(
  label,
  action,
  {
    log,
    t,
    allowRetry = true,
    retryDelaysMs = [900, 1600],
    fallbackMessage = "Blad wywolania API.",
    unavailableHint = "OqlOS chwilowo niedostepny",
    retryInHint = "ponawiam za",
    noRetryI18nKey = "hardwareRestart.probeNoQuickRetry",
  } = {},
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
          const gatewayErr = new Error(`${message} (${t(noRetryI18nKey)})`);
          gatewayErr.status = err?.status;
          gatewayErr.body = err?.body;
          throw gatewayErr;
        }
        throw err;
      }
      const waitMs = retryDelaysMs[attempt];
      if (typeof log === "function") {
        log(`${label}: ${unavailableHint} (${message}), ${retryInHint} ${waitMs} ms...`);
      }
      await sleep(waitMs);
      attempt += 1;
    }
  }
}

export { RETRYABLE_HTTP_STATUSES };

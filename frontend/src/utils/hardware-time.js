/** Local time string for hardware demo/status activity logs. */
export function hardwareNowText() {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

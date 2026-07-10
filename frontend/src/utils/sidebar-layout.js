/** Keep in sync with `--oqlos-sidebar-width` / `--oqlos-sidebar-rail-width` in global.css */
export const OQLOS_SIDEBAR_WIDTH_PX = 280;
export const OQLOS_SIDEBAR_RAIL_WIDTH_PX = 10;

export function oqlosSidebarWidthCss() {
  return `${OQLOS_SIDEBAR_WIDTH_PX}px`;
}

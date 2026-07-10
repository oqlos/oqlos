import test from "node:test";
import assert from "node:assert/strict";

import { OQLOS_SIDEBAR_RAIL_WIDTH_PX, OQLOS_SIDEBAR_WIDTH_PX, oqlosSidebarWidthCss } from "./sidebar-layout.js";

test("sidebar layout tokens match global.css chrome width", () => {
  assert.equal(OQLOS_SIDEBAR_WIDTH_PX, 280);
  assert.equal(OQLOS_SIDEBAR_RAIL_WIDTH_PX, 10);
  assert.equal(oqlosSidebarWidthCss(), "280px");
});

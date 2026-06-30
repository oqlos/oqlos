import { Link, useLocation } from "react-router-dom";
import { canConnectRoleAccessPath } from "../utils/rbac.policy.js";
import { useAppConfig } from "../context/AppConfigProvider";
import { useI18n } from "../i18n/I18nProvider";

const navItems = [
  { path: "/hardware-status", labelKey: "nav.hardware" },
  { path: "/hardware-demo", labelKey: "nav.demo" },
  { path: "/scenario-files", labelKey: "nav.scenarioFiles" },
  { path: "/map-editor", labelKey: "nav.map" },
  { path: "/func-editor", labelKey: "nav.func" },
];

export default function SharedNav({
  navContext = null,
  viewTabs = null,
  viewMode = null,
  onViewModeChange = null,
  viewModeAriaLabel = "",
}) {
  const location = useLocation();
  const { role } = useAppConfig();
  const { t } = useI18n();
  const currentPath = location.pathname;
  const visibleNavItems = navItems.filter((item) => canConnectRoleAccessPath(item.path, role));
  const hasViewTabs = Array.isArray(viewTabs) && viewTabs.length > 0 && typeof onViewModeChange === "function";

  return (
    <nav className="nav">
      {navContext ? <div className="nav-context">{navContext}</div> : null}
      <div className="nav-menu">
        {visibleNavItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`nav-link nav-route-link ${currentPath === item.path || currentPath.startsWith(item.path + "/") ? "active" : ""}`}
          >
            {t(item.labelKey)}
          </Link>
        ))}
        {hasViewTabs ? (
          <>
            {visibleNavItems.length > 0 ? <span className="nav-menu-divider" aria-hidden="true" /> : null}
            <div
              className="nav-view-toggle"
              role="tablist"
              aria-label={viewModeAriaLabel}
            >
              {viewTabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={viewMode === tab.id}
                  className={`nav-view-tab role-force ${viewMode === tab.id ? "active" : ""}`}
                  onClick={() => onViewModeChange(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </>
        ) : null}
      </div>
    </nav>
  );
}

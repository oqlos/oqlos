import { Link, useLocation } from "react-router-dom";
import { canConnectRoleAccessPath } from "../utils/rbac.policy.js";
import { useAppConfig } from "../context/AppConfigProvider";
import { useI18n } from "../i18n/I18nProvider";

const navItems = [
  { path: "/hardware-status", labelKey: "nav.hardware" },
  { path: "/hardware-restart", labelKey: "nav.restart" },
  { path: "/hardware-demo", labelKey: "nav.demo" },
  { path: "/scenario-files", labelKey: "nav.scenarioFiles" },
  { path: "/map-editor", labelKey: "nav.map" },
  { path: "/func-editor", labelKey: "nav.func" },
  { path: "/motor-services", labelKey: "nav.motorServices" },
  { href: "/ui/panel", labelKey: "nav.panel" },
  { href: "/ui/navigation", labelKey: "nav.navigation" },
  { href: "/docs", labelKey: "nav.apiDocs" },
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
  const visibleNavItems = navItems.filter((item) => canConnectRoleAccessPath(item.path || item.href, role));
  const hasViewTabs = Array.isArray(viewTabs) && viewTabs.length > 0 && typeof onViewModeChange === "function";
  const hostLabel = typeof window !== "undefined" ? window.location.host : "OqlOS";

  const renderNavItem = (item) => {
    const itemPath = item.path || item.href;
    const active = item.path ? currentPath === item.path || currentPath.startsWith(`${item.path}/`) : false;
    const className = `nav-link nav-route-link ${active ? "active" : ""}`;
    if (item.href) {
      return (
        <a key={item.href} href={item.href} className={className}>
          {t(item.labelKey)}
        </a>
      );
    }
    return (
      <Link key={itemPath} to={item.path} className={className}>
        {t(item.labelKey)}
      </Link>
    );
  };

  return (
    <nav className="nav">
      <div className="nav-brand">
        <a href="/ui/navigation" className="nav-brand-title">OqlOS</a>
        <span className="nav-brand-host">{hostLabel}</span>
      </div>
      {navContext ? <div className="nav-context">{navContext}</div> : null}
      <div className="nav-menu">
        {visibleNavItems.map(renderNavItem)}
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

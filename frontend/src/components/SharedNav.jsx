import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { canConnectRoleAccessPath } from "../utils/rbac.policy.js";
import { useAppConfig } from "../context/AppConfigProvider";
import { useI18n } from "../i18n/I18nProvider";
import { preserveUiNavSearchParams } from "../utils/ui-url-args-cookie.js";

const navItems = [
  { path: "/status", labelKey: "nav.hardware" },
  { path: "/hardware-modbus", labelKey: "nav.modbus" },
  { path: "/hardware-coils", labelKey: "nav.coilTest" },
  { path: "/hardware-rtc", labelKey: "nav.rtc" },
  { path: "/motor-services", labelKey: "nav.motorServices" },
  { path: "/scenario-files", labelKey: "nav.scenarioFiles" },
  { path: "/map-editor", labelKey: "nav.map" },
  { path: "/func-editor", labelKey: "nav.func" },
  { path: "/panel", labelKey: "nav.panel" },
  { path: "/api-docs", labelKey: "nav.apiDocs" },
];

export default function SharedNav({
  navContext = null,
  viewTabs = null,
  viewMode = null,
  onViewModeChange = null,
  viewModeAriaLabel = "",
}) {
  const location = useLocation();
  const config = useAppConfig();
  const { role, patch, iframeChild } = config;
  const { t } = useI18n();
  const currentPath = location.pathname;
  const visibleNavItems = navItems.filter((item) => canConnectRoleAccessPath(item.path || item.href, role));
  const hasViewTabs = Array.isArray(viewTabs) && viewTabs.length > 0 && typeof onViewModeChange === "function";
  const hostLabel = typeof window !== "undefined" ? window.location.host : "OqlOS";

  const [sidebarState, setSidebarState] = useState(() => {
    return window.__activeSidebar
      ? { active: true, collapsed: window.__activeSidebar.collapsed }
      : { active: false, collapsed: false };
  });

  useEffect(() => {
    if (window.__activeSidebar) {
      setSidebarState({
        active: true,
        collapsed: window.__activeSidebar.collapsed,
      });
    }

    const handleRegister = () => {
      setSidebarState(
        window.__activeSidebar
          ? { active: true, collapsed: window.__activeSidebar.collapsed }
          : { active: false, collapsed: false }
      );
    };
    window.addEventListener("oqlos-sidebar-registered", handleRegister);
    return () => window.removeEventListener("oqlos-sidebar-registered", handleRegister);
  }, []);

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
      <Link key={itemPath} to={preserveUiNavSearchParams(item.path, location.search)} className={className}>
        {t(item.labelKey)}
      </Link>
    );
  };

  return (
    <nav className="nav">
      <div className="nav-top">
        <div className="nav-top-start">
          {sidebarState.active && (
            <button
              type="button"
              className={`nav-control-btn sidebar-toggle-btn role-force ${sidebarState.collapsed ? "active" : ""}`}
              onClick={() => window.__activeSidebar?.toggleCollapsed()}
              title={t("topbar.sidebar-toggle", "Pokaż/ukryj panel boczny")}
              aria-pressed={sidebarState.collapsed ? "true" : "false"}
            >
              ☰
            </button>
          )}
          <div className="nav-brand">
            <Link to={preserveUiNavSearchParams("/status", location.search)} className="nav-brand-title">OqlOS</Link>
            <span className="nav-brand-host">{hostLabel}</span>
          </div>
          {navContext ? <div className="nav-context">{navContext}</div> : null}
        </div>
        {!iframeChild && (
          <div className="nav-controls">
            <label className="nav-control-label" htmlFor="nav-input-mode-select">
            <select
              id="nav-input-mode-select"
              className="nav-control-select"
              value={config.mode || "keyboard"}
              onChange={(e) => patch({ mode: e.target.value })}
              title={t("topbar.input-mode.title", "Tryb sterowania")}
            >
              <option value="keyboard">KEYBOARD</option>
              <option value="encoder">ENCODER</option>
              <option value="scanner">SCANNER</option>
            </select>
          </label>

          <div className="connect-font-control">
            <button
              type="button"
              data-size="default"
              className={`cf-btn cf-md role-force ${config.font === "default" ? "active" : ""}`}
              onClick={() => patch({ font: "default" })}
              title={t("font.size.default", "Domyślna czcionka")}
            >
              A
            </button>
            <button
              type="button"
              data-size="large"
              className={`cf-btn cf-lg role-force ${config.font === "large" ? "active" : ""}`}
              onClick={() => patch({ font: "large" })}
              title={t("font.size.large", "Duża czcionka")}
            >
              A+
            </button>
            <button
              type="button"
              data-size="xlarge"
              className={`cf-btn cf-xl role-force ${config.font === "xlarge" ? "active" : ""}`}
              onClick={() => patch({ font: "xlarge" })}
              title={t("font.size.xlarge", "Bardzo duża czcionka")}
            >
              A++
            </button>
          </div>

          <select
            className="nav-control-select theme-select"
            value={config.theme}
            onChange={(e) => patch({ theme: e.target.value })}
            title={t("topbar.theme-title", "Motyw UI")}
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
            <option value="high-contrast">High Contrast</option>
          </select>

          <select
            className="nav-control-select lang-select"
            value={config.lang}
            onChange={(e) => patch({ lang: e.target.value })}
            title={t("topbar.lang-title", "Język")}
          >
            <option value="pl">PL</option>
            <option value="en">EN</option>
            <option value="de">DE</option>
            <option value="ru">RU</option>
            <option value="ua">UA</option>
            <option value="cs">CS</option>
          </select>

          <button
            type="button"
            className="nav-control-btn size-toggle-btn role-force"
            onClick={() => {
              const params = new URLSearchParams(window.location.search);
              const rawSize = params.get("size");
              const nextSize = rawSize === "100" ? 1280 : 100;
              patch({ size: nextSize });
            }}
            title={t("topbar.toggle-view", "Zmień rozmiar widoku")}
          >
            {new URLSearchParams(window.location.search).get("size") === "100" ? "1280×800" : "100%"}
          </button>
          </div>
        )}
      </div>
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

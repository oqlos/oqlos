import { useCallback, useEffect, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { dedupeNavigationPages, normalizeUiPagePath, uiPageHref } from "../utils/ui-url-args-cookie.js";

export default function NodeNavigationPanel({ refreshToken = 0, embedded = false }) {
  const { t } = useI18n();
  const [navData, setNavData] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [navRes, healthRes] = await Promise.all([
        fetch("/api/v1/navigation"),
        fetch("/health"),
      ]);
      if (!navRes.ok) throw new Error(`navigation HTTP ${navRes.status}`);
      const nav = await navRes.json();
      const health = healthRes.ok ? await healthRes.json() : null;

      setNavData(nav);
      setHealthData(health);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData, refreshToken]);

  const healthBadgeText = healthData?.status === "ok" ? "healthy" : navData ? "navigation loaded" : "error";
  const healthBadgeCls = healthData?.status === "ok" ? "badge--ok" : "badge--warn";
  const hostLabel = typeof window !== "undefined" ? window.location.host : "OqlOS";

  return (
    <section className={embedded ? "nav-index-embedded" : "nav-index-section"}>
      {error ? <div className="mapx-error">{error}</div> : null}

      <div className="nav-index-hero">
        <div className="hw-card">
          <h3>{t("navigationIndex.heroTitle", "OqlOS BoardNet navigation")}</h3>
          <p className="nav-index-lead">
            {t("navigationIndex.heroLead", "Jeden punkt wejścia do oprogramowania węzła Raspberry Pi. Dostępny pod adresem:")}{" "}
            <code>{hostLabel}</code>.
          </p>
        </div>
        <div className="hw-card nav-index-status-card">
          <h3>{t("navigationIndex.nodeStatus", "Status węzła")}</h3>
          <div>
            <span className={`badge ${healthBadgeCls}`}>{healthBadgeText}</span>
            {loading ? <span className="nav-index-meta"> …</span> : null}
          </div>
          {navData ? (
            <div className="nav-index-meta">
              node={navData.node_id || "unknown"} role={navData.role || "off"} service={navData.service || "oqlos"} version={navData.version || "unknown"}
            </div>
          ) : null}
        </div>
      </div>

      <div className="nav-index-grid" style={{ marginBottom: "14px" }}>
        <div className="hw-card">
          <h3>{t("navigationIndex.userPages", "Strony dla użytkownika")}</h3>
          <div className="nav-index-list">
            {dedupeNavigationPages(navData?.pages).map((p) => (
              <div key={p.path} className="nav-index-row">
                <a href={uiPageHref(p.path)} className="nav-index-link">
                  {p.label || p.path}
                </a>
                <span className="nav-index-desc">{p.description}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="hw-card">
          <h3>{t("navigationIndex.aliases", "Skróty (Aliasy)")}</h3>
          <div className="nav-index-list">
            {navData?.aliases?.map((a) => (
              <div key={a.path} className="nav-index-row nav-index-row--stacked">
                <a href={uiPageHref(a.path)} className="nav-index-link nav-index-link--plain">
                  {a.path}
                </a>
                <span className="nav-index-alias-target">
                  {t("navigationIndex.redirectsTo", "Przekierowuje do:")}{" "}
                  <code>{normalizeUiPagePath(a.target)}</code>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="hw-card" style={{ marginBottom: "14px" }}>
        <h3>{t("navigationIndex.apiEndpoints", "Punkty końcowe API")}</h3>
        <div className="hw-table-wrap nav-index-code">
          <table className="hw-table">
            <thead>
              <tr>
                <th>{t("navigationIndex.method", "Metoda")}</th>
                <th>{t("navigationIndex.path", "Ścieżka")}</th>
                <th>{t("navigationIndex.description", "Opis")}</th>
              </tr>
            </thead>
            <tbody>
              {navData?.api?.map((api, idx) => (
                <tr key={idx}>
                  <td>
                    <span className="badge badge--method">{api.method}</span>
                  </td>
                  <td>
                    <code className="text-sm text-mono">{api.path}</code>
                  </td>
                  <td className="text-muted text-sm">{api.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="nav-index-grid">
        <div className="hw-card">
          <h3>{t("navigationIndex.oqlHttpTitle", "Wywoływanie OQL przez HTTP")}</h3>
          <p className="nav-index-note">
            {t("navigationIndex.oqlHttpNote", "Używaj trybu execute tylko gdy sprzęt jest gotowy i komenda jest celowa.")}
          </p>
          <pre className="hw-pre nav-index-code">
            {`BASE=http://${hostLabel}\ncurl -s -X POST "$BASE/api/v1/oql/execute" \\\n  -H 'Content-Type: application/json' \\\n  -d '{"kind":"command","mode":"execute","oql":"SET \\"pump\\" \\"25\\""}'`}
          </pre>
        </div>

        <div className="hw-card">
          <h3>{t("navigationIndex.diagnosticsTitle", "Uruchamianie diagnostyki")}</h3>
          <p className="nav-index-note">
            {t("navigationIndex.diagnosticsNote", "Czasowniki zarządzania (manage verbs) to najszybszy sposób na weryfikację wykrywania oprogramowania układowego i sprzętu.")}
          </p>
          <pre className="hw-pre nav-index-code">
            {`BASE=http://${hostLabel}\ncurl -s -X POST "$BASE/api/v1/oql/manage" \\\n  -H 'Content-Type: application/json' \\\n  -d '{"verb":"health","args":{"scan":"never"}}'\n\ncurl -s -X POST "$BASE/api/v1/oql/manage" \\\n  -H 'Content-Type: application/json' \\\n  -d '{"verb":"usb-list"}'`}
          </pre>
        </div>
      </div>
    </section>
  );
}

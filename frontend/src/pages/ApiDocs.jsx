import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import SharedNav from "../components/SharedNav";
import { useI18n } from "../i18n/I18nProvider";
import { buildApiDocsIframeSrc } from "../utils/api-docs-url.js";

export default function ApiDocs() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const iframeSrc = useMemo(
    () => buildApiDocsIframeSrc(searchParams.toString()),
    [searchParams],
  );

  const navContext = (
    <div className="section-label" style={{ marginBottom: 0 }}>
      {t("nav.apiDocs", "API")}
    </div>
  );

  return (
    <div className="dashboard api-docs-shell">
      <SharedNav navContext={navContext} />
      <div className="api-docs-frame-wrap">
        <iframe
          className="api-docs-frame"
          src={iframeSrc}
          title={t("apiDocs.iframeTitle", "OqlOS API documentation")}
          loading="eager"
        />
      </div>
    </div>
  );
}

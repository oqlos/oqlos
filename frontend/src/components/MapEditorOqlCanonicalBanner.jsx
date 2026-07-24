import { connectOqlSystemUrl, oqlStoreFileUrl } from "../utils/mapEditorOqlCanonical.js";

/**
 * Banner: this MAP tab is read-only; edit OQL in connect-oql-system.
 */
export function MapEditorOqlCanonicalBanner({ t, info, legacyUnlocked = false }) {
  if (!info?.fileId) return null;
  const connectUrl = connectOqlSystemUrl(info.fileId);
  const storeUrl = oqlStoreFileUrl(info.fileId);
  return (
    <div className="mapx-oql-canonical-banner" role="status">
      <div className="mapx-oql-canonical-banner__title">
        {t(
          "mapEditor.oqlCanonicalTitle",
          "Źródło kanoniczne: OQL (map-editor tylko podgląd)"
        )}
        {info.slice ? (
          <span className="mapx-oql-canonical-banner__slice"> slice {info.slice}</span>
        ) : null}
      </div>
      <p className="mapx-oql-canonical-banner__body">
        {t(
          "mapEditor.oqlCanonicalBody",
          "Ta sekcja MAP jest zmigrowana do pliku OQL. Edycja trwała: menu systemowe connect-oql-system lub oql-store."
        )}
      </p>
      <div className="mapx-oql-canonical-banner__links">
        <a className="mapx-btn mapx-oql-canonical-banner__link" href={connectUrl} target="_blank" rel="noreferrer">
          {t("mapEditor.oqlCanonicalOpenEditor", "Otwórz w connect-oql-system")}
        </a>
        <a className="mapx-btn mapx-oql-canonical-banner__link" href={storeUrl} target="_blank" rel="noreferrer">
          {t("mapEditor.oqlCanonicalOpenApi", "API oql-store")}
        </a>
        <code className="mapx-oql-canonical-banner__file">{info.fileId}</code>
      </div>
      {legacyUnlocked ? (
        <p className="mapx-oql-canonical-banner__warn">
          {t(
            "mapEditor.oqlCanonicalLegacyOn",
            "legacy_edit=1 — zapis MAP odblokowany (tylko awaryjnie)."
          )}
        </p>
      ) : (
        <p className="mapx-oql-canonical-banner__hint">
          {t(
            "mapEditor.oqlCanonicalLegacyHint",
            "Awaryjny zapis MAP: dodaj ?legacy_edit=1 (rola system/admin)."
          )}
        </p>
      )}
    </div>
  );
}

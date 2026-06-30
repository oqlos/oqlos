import { META_FIELDS } from "../pages/mapEditorConstants.js";

export function MapEditorIntegrationMetaPanel({
  detailCfg,
  integrationMeta,
  onEditField,
  isReadOnly,
  t,
}) {
  if (!detailCfg) return null;
  return (
    <div className="mapx-meta-box">
      <div className="mapx-meta-title">{t("mapEditor.integrationMeta")}</div>
      <div className="mapx-meta-grid">
        {META_FIELDS.map((field) => (
          <div key={field} className="mapx-meta-row">
            <span className="mapx-meta-label">{t(`mapEditor.meta.${field}`)}</span>
            <span className="mapx-meta-value">{integrationMeta[field] || "—"}</span>
            <button
              type="button"
              className="mapx-btn"
              onClick={() => onEditField(field)}
              disabled={isReadOnly}
            >
              {t("mapEditor.editMeta")}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

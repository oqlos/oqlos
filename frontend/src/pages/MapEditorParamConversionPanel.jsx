import { ensureParamConversion } from "../utils/mapEditorModel.js";

export function MapEditorParamConversionPanel({
  target,
  isReadOnly,
  t,
  onEditAlgorithm,
  onEditField,
}) {
  if (!target || typeof target !== "object") return null;
  const view = structuredClone(target);
  ensureParamConversion(view);

  const rows = [
    { label: "Algorytm", value: view.conversionAlgorithm, onClick: onEditAlgorithm },
    { label: "Skala", value: view.conversionScale, onClick: () => onEditField("conversionScale", "number") },
    { label: "Offset", value: view.conversionOffset, onClick: () => onEditField("conversionOffset", "number") },
    { label: "Wzor (x = napiecie)", value: view.conversionExpression || "x", onClick: () => onEditField("conversionExpression") },
    { label: "Jednostka wejscia", value: view.conversionInputUnit, onClick: () => onEditField("conversionInputUnit") },
    { label: "Jednostka wyjscia", value: view.conversionOutputUnit, onClick: () => onEditField("conversionOutputUnit") },
  ];

  return (
    <div className="mapx-meta-box">
      <div className="mapx-meta-title">Przeliczanie wartosci (mapowanie)</div>
      <div className="mapx-meta-grid">
        {rows.map((row) => (
          <div key={row.label} className="mapx-meta-row">
            <span className="mapx-meta-label">{row.label}</span>
            <span className="mapx-meta-value">{row.value}</span>
            <button type="button" className="mapx-btn" onClick={row.onClick} disabled={isReadOnly}>
              {t("mapEditor.editMeta")}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

import { useMemo } from "react";
import { PARAM_CONVERSION_ALGORITHMS } from "./mapEditorConstants.js";
import { ensureParamConversion } from "../utils/mapEditorModel.js";
import {
  ADC_PREVIEW_SAMPLE,
  DEFAULT_ADC_PER_VOLT,
  PARAM_INPUT_UNITS,
  PARAM_OUTPUT_UNITS,
  formatConversionPreview,
  formatSignedConversionPreview,
  isAdcParamEntry,
  linearConversionHint,
} from "../utils/mapEditorParamConversion.js";

function parseNumberInput(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function MapEditorParamConversionPanel({
  target,
  isReadOnly,
  onChange,
}) {
  const view = useMemo(() => {
    const cloned = structuredClone(target || {});
    ensureParamConversion(cloned);
    return cloned;
  }, [target]);

  if (!target || typeof target !== "object") return null;

  const adcSensor = isAdcParamEntry(view);
  const preview = formatConversionPreview(ADC_PREVIEW_SAMPLE, view);
  const signedPreview = view.conversionAlgorithm === "linear"
    ? formatSignedConversionPreview(ADC_PREVIEW_SAMPLE, view)
    : "";
  const outputUnit = view.conversionOutputUnit || view.unit || "mbar";
  const inputUnit = view.conversionInputUnit || "ADC";

  const patch = (fields) => {
    if (isReadOnly) return;
    onChange(fields);
  };

  return (
    <div className="mapx-meta-box mapx-conversion-panel">
      <div className="mapx-meta-title">
        {adcSensor ? "Przeliczanie ADC → jednostka fizyczna" : "Przeliczanie wartosci (mapowanie)"}
      </div>

      <div className="mapx-conversion-form">
        <label className="mapx-conversion-field">
          <span className="mapx-meta-label">Tryb</span>
          <select
            className="mapx-conversion-input"
            value={view.conversionAlgorithm || "identity"}
            disabled={isReadOnly}
            onChange={(e) => patch({ conversionAlgorithm: e.target.value })}
          >
            <option value="identity">Bez przeliczenia (raw ADC)</option>
            <option value="linear">Liniowe ze punktem zerowym (±)</option>
            <option value="custom">Wzor wlasny (x = wejście)</option>
            {PARAM_CONVERSION_ALGORITHMS.includes("lookup") && (
              <option value="lookup" disabled>lookup (w przygotowaniu)</option>
            )}
          </select>
        </label>

        {view.conversionAlgorithm === "linear" && (
          <>
            <label className="mapx-conversion-field">
              <span className="mapx-meta-label">Jednostka wejścia</span>
              <select
                className="mapx-conversion-input"
                value={inputUnit}
                disabled={isReadOnly}
                onChange={(e) => patch({
                  conversionInputUnit: e.target.value,
                  ...(e.target.value === "V" && view.conversionAdcPerVolt === undefined
                    ? { conversionAdcPerVolt: DEFAULT_ADC_PER_VOLT }
                    : {}),
                })}
              >
                {PARAM_INPUT_UNITS.map((unit) => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
            </label>

            {inputUnit === "V" && (
              <label className="mapx-conversion-field">
                <span className="mapx-meta-label">ADC na 1 V</span>
                <input
                  type="number"
                  step="any"
                  min="0"
                  className="mapx-conversion-input"
                  value={view.conversionAdcPerVolt ?? DEFAULT_ADC_PER_VOLT}
                  disabled={isReadOnly}
                  onChange={(e) => patch({ conversionAdcPerVolt: parseNumberInput(e.target.value) })}
                />
              </label>
            )}

            <label className="mapx-conversion-field">
              <span className="mapx-meta-label">Punkt zerowy (0 ciśnienia)</span>
              <input
                type="number"
                step="any"
                className="mapx-conversion-input"
                value={view.conversionZeroPoint ?? 0}
                disabled={isReadOnly}
                placeholder={inputUnit === "V" ? "np. 2.0" : "np. 7900"}
                onChange={(e) => patch({ conversionZeroPoint: parseNumberInput(e.target.value) })}
              />
            </label>

            <label className="mapx-conversion-field">
              <span className="mapx-meta-label">Mnożnik (na jednostkę wejścia)</span>
              <input
                type="number"
                step="any"
                className="mapx-conversion-input"
                value={view.conversionScale ?? 1}
                disabled={isReadOnly}
                placeholder={inputUnit === "V" ? "np. 34 mbar/V" : "np. 0.01"}
                onChange={(e) => patch({ conversionScale: parseNumberInput(e.target.value) })}
              />
            </label>

            <label className="mapx-conversion-field">
              <span className="mapx-meta-label">Offset (dopasowanie)</span>
              <input
                type="number"
                step="any"
                className="mapx-conversion-input"
                value={view.conversionOffset ?? 0}
                disabled={isReadOnly}
                onChange={(e) => patch({ conversionOffset: parseNumberInput(e.target.value) })}
              />
            </label>

            <label className="mapx-conversion-field">
              <span className="mapx-meta-label">Jednostka wyjścia</span>
              <select
                className="mapx-conversion-input"
                value={outputUnit}
                disabled={isReadOnly}
                onChange={(e) => patch({
                  conversionOutputUnit: e.target.value,
                  unit: e.target.value,
                })}
              >
                {PARAM_OUTPUT_UNITS.map((unit) => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
            </label>
          </>
        )}

        {view.conversionAlgorithm === "custom" && (
          <label className="mapx-conversion-field mapx-conversion-field--wide">
            <span className="mapx-meta-label">Wzor (x = wejście po normalizacji)</span>
            <input
              type="text"
              className="mapx-conversion-input"
              value={view.conversionExpression || "x"}
              disabled={isReadOnly}
              placeholder="np. (x - 2) * 34"
              onChange={(e) => patch({ conversionExpression: e.target.value })}
            />
          </label>
        )}

        <div className="mapx-conversion-preview" aria-live="polite">
          <span className="mapx-meta-label">Podgląd</span>
          <span className="mapx-meta-value">{preview}</span>
        </div>

        {signedPreview && (
          <div className="mapx-conversion-preview" aria-live="polite">
            <span className="mapx-meta-label">Poniżej / powyżej zera</span>
            <span className="mapx-meta-value">{signedPreview}</span>
          </div>
        )}

        {view.conversionAlgorithm === "linear" && (
          <p className="mapx-conversion-hint">
            Wzór: <code>{linearConversionHint(view)}</code>
            <br />
            Poniżej punktu zerowego wynik jest ujemny, powyżej dodatni (np. 2&nbsp;V&nbsp;=&nbsp;0&nbsp;mbar).
          </p>
        )}
      </div>
    </div>
  );
}

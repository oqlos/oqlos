import { tic249RawTargetVelocity } from "../utils/mapEditorTic249.js";

const MOTOR_RUNTIME_FIELDS = [
  { labelKey: "mapEditor.motorStrokeSteps", field: "strokeSteps", suffix: " steps", type: "number" },
  { labelKey: "mapEditor.motorCycleVolume", field: "cycleVolumeLiters", suffix: " l", type: "number" },
  { labelKey: "mapEditor.motorMaxSpeed", field: "maxStepsPerSecond", suffix: " steps/s", type: "number" },
  { labelKey: "mapEditor.motorDefaultSpeed", field: "defaultSpeedStepsPerSecond", suffix: " steps/s", type: "number" },
  { labelKey: "mapEditor.motorAcceleration", field: "accelerationPercentPerSecond", suffix: " %/s", type: "number" },
  { labelKey: "mapEditor.motorSpeedUnit", field: "speedUnit", suffix: "", type: "text" },
  { labelKey: "mapEditor.motorLimitMode", field: "limitMode", suffix: "", type: "text" },
  { labelKey: "mapEditor.motorStartDirection", field: "startDirection", suffix: "", type: "text" },
];

export function MapEditorMotorRuntimePanel({ motorConfig, isReadOnly, onEditField, t }) {
  const cfg = motorConfig || {};
  return (
    <div className="mapx-meta-box">
      <div className="mapx-meta-title">{t("mapEditor.motorRuntimeTitle")}</div>
      <div className="mapx-meta-grid">
        {MOTOR_RUNTIME_FIELDS.map(({ labelKey, field, suffix, type }) => (
          <div key={field} className="mapx-meta-row">
            <span className="mapx-meta-label">{t(labelKey)}</span>
            <span className="mapx-meta-value">{cfg[field] ?? "—"}{suffix}</span>
            <button
              type="button"
              className="mapx-btn"
              onClick={() => onEditField(field, type)}
              disabled={isReadOnly}
            >
              {t("mapEditor.editMeta")}
            </button>
          </div>
        ))}
        <div className="mapx-meta-row">
          <span className="mapx-meta-label">{t("mapEditor.motorRawTargetVelocity")}</span>
          <span className="mapx-meta-value">{tic249RawTargetVelocity(cfg.defaultSpeedStepsPerSecond)}</span>
        </div>
      </div>
    </div>
  );
}

const MOTOR_RELATIVE_ARGS = [
  ["steps", "number"],
  ["direction", "text"],
  ["offset", "number"],
  ["speed", "number"],
  ["max_steps_per_second", "number"],
  ["acceleration", "number"],
];

function _motorArgLabel(argName, args) {
  if (argName === "max_steps_per_second") return `limit: ${args.max_steps_per_second ?? "—"} steps/s`;
  if (argName === "acceleration") return `accel: ${args.acceleration ?? "—"}%/s`;
  return `${argName}: ${args[argName] ?? "—"}`;
}

function _MotorRelativeParams({ args, actionName, onEditArg, isReadOnly }) {
  return (
    <div className="mapx-action-params">
      {MOTOR_RELATIVE_ARGS.map(([argName, type]) => (
        <button
          key={argName}
          type="button"
          className="mapx-param-pill"
          onClick={() => onEditArg(actionName, argName, type)}
          disabled={isReadOnly}
        >
          {_motorArgLabel(argName, args)}
        </button>
      ))}
    </div>
  );
}

function _GenericActionParams({ body, actionName, onEditBodyField, isReadOnly }) {
  return (
    <div className="mapx-action-params">
      <button type="button" className="mapx-param-pill" onClick={() => onEditBodyField(actionName, "peripheral_id")} disabled={isReadOnly}>
        peripheral: {body.peripheral_id || "—"}
      </button>
      <button type="button" className="mapx-param-pill" onClick={() => onEditBodyField(actionName, "command")} disabled={isReadOnly}>
        command: {body.command || "—"}
      </button>
    </div>
  );
}

export function MapEditorObjectActionPanel({ objectCfg, isReadOnly, onEditArg, onEditBodyField }) {
  if (!objectCfg || typeof objectCfg !== "object") return null;
  return (
    <div className="mapx-meta-box">
      <div className="mapx-meta-title">Akcje i parametry</div>
      <div className="mapx-action-list">
        {Object.entries(objectCfg).map(([actionName, binding]) => {
          const args = binding?.args && typeof binding.args === "object" ? binding.args : {};
          const body = binding?.body && typeof binding.body === "object" ? binding.body : {};
          const isRelativeMotorMove = body.peripheral_id === "motor-tic249" && body.command === "move_relative";
          return (
            <div key={actionName} className="mapx-action-row">
              <div className="mapx-action-main">
                <strong>{actionName}</strong>
                <span>{body.peripheral_id || "—"} / {body.command || "—"}</span>
              </div>
              {isRelativeMotorMove
                ? <_MotorRelativeParams args={args} actionName={actionName} onEditArg={onEditArg} isReadOnly={isReadOnly} />
                : <_GenericActionParams body={body} actionName={actionName} onEditBodyField={onEditBodyField} isReadOnly={isReadOnly} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

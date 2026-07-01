const TOP_LEVEL_GOAL_RE = /^GOAL:\s*(.*)$/i;
const SET_NAME_RE = /^\s*SET\s+NAME\s+(?:(['"])(.*?)\1|(.+?))\s*$/i;
const WAIT_RE = /\b(?:SET\s+)?WAIT\s+['"]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(ms|millisecond|milliseconds|s|sec|second|seconds|min|minute|minutes|m)?\s*['"]?/gi;

function normalizeSource(source) {
  return String(source ?? "").replace(/\r\n?/g, "\n");
}

function goalTitleFromLines(lines, fallback) {
  const firstLineTitle = lines[0]?.match(TOP_LEVEL_GOAL_RE)?.[1]?.trim();
  if (firstLineTitle) return firstLineTitle;

  for (const line of lines) {
    const match = line.match(SET_NAME_RE);
    if (match) {
      return (match[2] || match[3] || "").trim() || fallback;
    }
  }
  return fallback;
}

export function splitOqlIntoGoalScripts(source) {
  const lines = normalizeSource(source).split("\n");
  const headerLines = [];
  const goals = [];
  let currentGoal = null;

  for (const line of lines) {
    if (TOP_LEVEL_GOAL_RE.test(line)) {
      if (currentGoal) goals.push(currentGoal);
      currentGoal = [line];
      continue;
    }

    if (currentGoal) {
      currentGoal.push(line);
    } else {
      headerLines.push(line);
    }
  }

  if (currentGoal) goals.push(currentGoal);

  if (goals.length === 0) {
    const script = normalizeSource(source).trimEnd();
    return script ? [{ index: 1, total: 1, name: "Cały scenariusz", script: `${script}\n` }] : [];
  }

  const header = headerLines.join("\n").trimEnd();
  return goals.map((goalLines, idx) => {
    const goal = goalLines.join("\n").trimEnd();
    const body = header ? `${header}\n\n${goal}` : goal;
    return {
      index: idx + 1,
      total: goals.length,
      name: goalTitleFromLines(goalLines, `GOAL ${idx + 1}`),
      script: `${body}\n`,
    };
  });
}

export function estimateOqlWaitMs(source) {
  let totalMs = 0;
  const text = normalizeSource(source);
  for (const match of text.matchAll(WAIT_RE)) {
    const value = Number.parseFloat(match[1].replace(",", "."));
    if (!Number.isFinite(value)) continue;
    const unit = (match[2] || "s").toLowerCase();
    if (unit === "ms" || unit.startsWith("millisecond")) {
      totalMs += value;
    } else if (unit === "min" || unit === "m" || unit.startsWith("minute")) {
      totalMs += value * 60_000;
    } else {
      totalMs += value * 1000;
    }
  }
  return Math.round(totalMs);
}

export function timeoutMsForOqlScript(source, speed = 1) {
  const numericSpeed = Number.parseFloat(speed);
  if (Number.isFinite(numericSpeed) && numericSpeed > 2) return 60_000;
  const waitMs = estimateOqlWaitMs(source);
  return Math.min(600_000, Math.max(60_000, waitMs + 30_000));
}

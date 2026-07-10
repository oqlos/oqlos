export const STATUS_LOG_URL_PARAM = "log";

const LOG_ID_RE = /^(file:[\w.-]+\.log(?:\.\d+)?|journal:[\w@.-]+\.service)$/;

export function readStatusLogFromSearch(search) {
  const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
  const token = String(params.get(STATUS_LOG_URL_PARAM) || "").trim();
  if (!token) return "";
  return LOG_ID_RE.test(token) ? token : "";
}

export function patchStatusLogSearchParams(params, logId) {
  const next = new URLSearchParams(params);
  const token = String(logId || "").trim();
  if (!token) {
    next.delete(STATUS_LOG_URL_PARAM);
  } else if (LOG_ID_RE.test(token)) {
    next.set(STATUS_LOG_URL_PARAM, token);
  }
  return next;
}

export function formatLogFileSize(bytes) {
  const size = Number(bytes) || 0;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function buildStatusLogSidebarItems(payload, t) {
  const items = [
    {
      id: "",
      title: t("hardware.statusLogs.overview"),
      subtitle: t("hardware.statusLogs.overviewHint"),
    },
  ];

  for (const group of payload?.groups || []) {
    items.push({
      id: `header:${group.day}`,
      kind: "header",
      title: group.day,
    });
    for (const file of group.files || []) {
      items.push({
        id: file.id,
        title: file.name,
        subtitle: formatLogFileSize(file.size_bytes),
      });
    }
  }

  const journalUnits = payload?.journal_units || [];
  if (journalUnits.length) {
    items.push({
      id: "header:journal",
      kind: "header",
      title: t("hardware.statusLogs.journalSection"),
    });
    for (const unit of journalUnits) {
      items.push({
        id: unit.id,
        title: unit.name,
        subtitle: "journalctl",
      });
    }
  }

  return items;
}

export function resolveStatusLogTitle(items, activeLogId, t) {
  if (!activeLogId) return t("hardware.statusLogs.overview");
  const match = items.find((item) => item.id === activeLogId);
  return match?.title || activeLogId;
}

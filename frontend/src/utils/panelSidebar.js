/** Build grouped sidebar items for the OQL panel scenario list. */
export function buildPanelSidebarItems({
  fileScenarios = [],
  myScenarios = [],
  builtinTemplates = [],
  serverScenarios = [],
}) {
  const items = [];
  const pushSection = (headerId, headerTitle, entries) => {
    if (entries.length === 0) return;
    items.push({ id: headerId, kind: "header", title: headerTitle });
    entries.forEach((entry) => items.push(entry));
  };

  pushSection(
    "__header__files",
    "Pliki scenariuszy",
    fileScenarios.map((s) => {
      const fileName = String(s._filePath || s.name || "").split("/").pop() || s.name;
      return {
        id: `file:${s._filePath}`,
        title: fileName,
        subtitle: s._filePath,
        _scenario: s,
      };
    }),
  );
  pushSection(
    "__header__my",
    "Moje scenariusze",
    myScenarios.map((s) => ({
      id: `my:${s.name}`,
      title: s.name,
      subtitle: "localStorage",
      _scenario: {
        name: s.name,
        oql: s.oql,
        _my: true,
        _name: s.name,
        _group: "Moje scenariusze",
      },
    })),
  );
  pushSection(
    "__header__tpl",
    "Szablony panelu",
    builtinTemplates.map((s) => ({
      id: `tpl:${s.name}`,
      title: s.name,
      subtitle: "wbudowany",
      _scenario: { ...s, _group: "Szablony panelu" },
    })),
  );
  pushSection(
    "__header__srv",
    "Serwer DB",
    serverScenarios.map((s) => ({
      id: `srv:${s.name}`,
      title: s.name,
      subtitle: s._group,
      _scenario: s,
    })),
  );
  return items;
}

export function isPanelScenarioHeaderId(id) {
  return String(id || "").startsWith("__header__");
}

export function isPanelScenarioFileId(id) {
  return String(id || "").startsWith("file:");
}

export function panelScenarioFilePath(id) {
  return isPanelScenarioFileId(id) ? String(id).slice(5) : "";
}

export function canDeletePanelScenario(id) {
  return isPanelScenarioFileId(id) || String(id || "").startsWith("my:");
}

export function isPanelEditorDirty({ selectedScenarioId, editorText, savedEditorText }) {
  return Boolean(selectedScenarioId) && editorText !== savedEditorText;
}

/** Returns true when scenario switch should proceed (no dirty guard or user confirmed). */
export function shouldProceedWithScenarioSwitch({
  selectedScenarioId,
  nextId,
  editorText,
  savedEditorText,
  confirmDiscard,
}) {
  if (!nextId || isPanelScenarioHeaderId(nextId)) return false;
  if (!selectedScenarioId || nextId === selectedScenarioId) return true;
  if (editorText === savedEditorText) return true;
  return Boolean(confirmDiscard?.());
}

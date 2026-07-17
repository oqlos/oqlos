import { useState } from "react";
import { rem } from "@semcod/frontend-services/designRem.js";
import { useSelectionCollapsePanel } from "../utils/useSelectionCollapsePanel.js";
import { useI18n } from "../i18n/I18nProvider";

export default function SidebarList({
  title,
  items = [],
  activeId,
  onSelect,
  count,
  searchPlaceholder = null,
  headerAddons,
  footer,
  onRefresh,
  collapseToggleId,
  collapseLabel,
  collapseStorageKey,
  collapseIcon = "☰",
  collapseOnSelect = true,
}) {
  const { t } = useI18n();
  const [filter, setFilter] = useState("");

  const collapseEnabled = Boolean(collapseToggleId);
  const selectableItems = items.filter((i) => i.kind !== "header");

  const {
    collapsed,
    userCollapsed,
    inIframe,
    scheduleCollapse,
    cancelAutoCollapse,
    toggleCollapsed,
    railEnter,
    railLeave,
    panelEnter,
    panelLeave,
    pinned,
    togglePinned,
  } = useSelectionCollapsePanel({
    toggleId: collapseToggleId || "",
    storageKey: collapseStorageKey || `ui.${collapseToggleId || "sidebar"}-collapsed`,
    label: collapseLabel || title,
    icon: collapseIcon,
    badge: count !== undefined ? count : selectableItems.length,
  });

  const inPreview = collapseEnabled && !collapsed && userCollapsed;

  const filtered = filter
    ? selectableItems.filter((i) =>
        (i.title || "").toLowerCase().includes(filter.toLowerCase())
        || (i.subtitle || "").toLowerCase().includes(filter.toLowerCase()))
    : items;

  const handleSelect = (id, item) => {
    if (item?.kind === "header") return;
    if (onSelect) onSelect(id, item);
    if (collapseEnabled && collapseOnSelect) scheduleCollapse();
  };

  if (collapseEnabled && collapsed) {
    return (
      <div
        className={`sidebar-list-panel collapsed${inIframe ? " collapsed--hosted" : ""}`}
        data-collapsed="1"
        data-toggle-hosted={inIframe ? "parent" : "self"}
      >
        <button
          type="button"
          className="sidebar-list-rail"
          onClick={toggleCollapsed}
          onMouseEnter={railEnter}
          onMouseLeave={railLeave}
          onFocus={railEnter}
          onBlur={railLeave}
          title={collapseLabel || title}
          aria-label={collapseLabel || title}
          aria-pressed="true"
        >
          <span aria-hidden="true" className="sidebar-list-rail-icon">{collapseIcon}</span>
        </button>
      </div>
    );
  }

  return (
    <div
      className={`sidebar-list-panel${inPreview ? " preview" : ""}`}
      data-collapsed="0"
      data-preview={inPreview ? "1" : "0"}
      onMouseEnter={inPreview ? panelEnter : undefined}
      onMouseLeave={inPreview ? panelLeave : undefined}
    >
      <div style={styles.header}>
        {collapseEnabled && (
          <button
            type="button"
            style={styles.collapseBtn}
            onClick={toggleCollapsed}
            title={t("sidebar.hideList", "Ukryj listę")}
            aria-label={t("sidebar.hideList", "Ukryj listę")}
          >
            «
          </button>
        )}
        <span style={styles.title}>{title}</span>
        {collapseEnabled && (
          <button
            type="button"
            style={{
              ...styles.pinBtn,
              opacity: pinned ? 1 : 0.4,
            }}
            onClick={togglePinned}
            title={pinned ? t("sidebar.unpin", "Odepnij listę") : t("sidebar.pin", "Przypnij listę")}
            aria-label={pinned ? t("sidebar.unpin", "Odepnij listę") : t("sidebar.pin", "Przypnij listę")}
          >
            📌
          </button>
        )}
        {(count !== undefined || selectableItems.length > 0) && (
          <span style={styles.count}>{count !== undefined ? count : selectableItems.length}</span>
        )}
        {onRefresh && (
          <button style={styles.iconBtn} onClick={onRefresh} title={t("sidebar.refresh", "Odśwież")}>↻</button>
        )}
        {headerAddons}
      </div>

      <div style={styles.searchWrap}>
        <input
          style={styles.search}
          placeholder={searchPlaceholder || t("sidebar.searchPlaceholder", "Szukaj…")}
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            if (collapseEnabled && e.target.value) cancelAutoCollapse();
          }}
        />
      </div>

      <div style={styles.list}>
        {filtered.length === 0 && (
          <div style={styles.msg}>{t("sidebar.noItems", "Brak elementów")}</div>
        )}
        {filtered.map((item) => {
          if (item.kind === "header") {
            return (
              <div key={item.id} style={styles.sectionHeader}>
                {item.title}
              </div>
            );
          }
          return (
          <div
            key={item.id}
            style={{
              ...styles.item,
              ...(activeId === item.id ? styles.itemActive : {}),
            }}
            onClick={() => handleSelect(item.id, item)}
          >
            <div style={styles.itemTitle}>{item.title}</div>
            {item.subtitle && (
              <div style={styles.itemMeta}>
                <span style={styles.itemId}>{item.subtitle}</span>
              </div>
            )}
            {item.extraNode}
          </div>
          );
        })}
      </div>
      {footer && <div style={styles.footer}>{footer}</div>}
    </div>
  );
}

const styles = {
  collapseBtn: {
    background: "none",
    border: "none",
    color: "var(--text-muted)",
    cursor: "pointer",
    padding: "2px 6px",
    fontSize: rem.base,
    lineHeight: 1,
  },
  pinBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: "2px 6px",
    fontSize: rem.sm,
    lineHeight: 1,
    transition: "opacity 0.15s ease",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    padding: "10px 10px 6px",
    borderBottom: "1px solid var(--border-color)",
  },
  title: {
    flex: 1,
    fontSize: rem.xs,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--text-muted)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  count: {
    fontSize: rem.xs,
    color: "var(--text-muted)",
    background: "var(--bg-deep)",
    borderRadius: "10px",
    padding: "1px 6px",
  },
  iconBtn: {
    background: "none",
    border: "none",
    color: "var(--text-muted)",
    cursor: "pointer",
    padding: "2px 4px",
    fontSize: rem.base,
    lineHeight: 1,
  },
  searchWrap: {
    padding: "6px 8px",
    borderBottom: "1px solid var(--border-color)",
  },
  search: {
    width: "100%",
    boxSizing: "border-box",
    background: "var(--bg-deep)",
    border: "1px solid var(--border-color)",
    borderRadius: "4px",
    padding: "4px 8px",
    fontSize: rem.sm,
    color: "var(--text-primary)",
    outline: "none",
  },
  list: {
    flex: 1,
    overflowY: "auto",
  },
  msg: {
    padding: "16px 12px",
    fontSize: rem.sm,
    color: "var(--text-muted)",
    textAlign: "center",
  },
  item: {
    position: "relative",
    padding: "8px 10px",
    cursor: "pointer",
    borderBottom: "1px solid var(--border-color)",
    transition: "background 0.1s",
  },
  sectionHeader: {
    padding: "8px 10px 4px",
    fontSize: rem.xxs,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--text-muted)",
    background: "var(--bg-deep)",
    borderBottom: "1px solid var(--border-color)",
    position: "sticky",
    top: 0,
    zIndex: 1,
  },
  itemActive: {
    background: "rgba(59,130,246,0.15)",
    borderLeft: "3px solid var(--accent-blue)",
    paddingLeft: "7px",
  },
  itemTitle: {
    fontSize: rem.md,
    color: "var(--text-primary)",
    fontWeight: 500,
    wordBreak: "break-word",
    whiteSpace: "normal",
    paddingRight: "10px",
  },
  itemMeta: {
    display: "flex",
    gap: "8px",
    marginTop: "2px",
  },
  itemId: {
    fontSize: rem.xxs,
    color: "var(--text-muted)",
    fontFamily: "var(--font-mono)",
  },
  footer: {
    padding: "8px",
    borderTop: "1px solid var(--border-color)",
  },
};

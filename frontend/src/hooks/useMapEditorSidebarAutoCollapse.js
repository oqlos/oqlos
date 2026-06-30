import { useEffect } from "react";

/** Auto-collapse map-editor sidebar on dense fonts + narrow viewports. */
export function useMapEditorSidebarAutoCollapse(setSidebarAutoCollapsed) {
  useEffect(() => {
    const applyAutoCollapse = () => {
      const root = document.documentElement;
      const font = String(root?.dataset?.font || "").trim().toLowerCase();
      const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1280;
      const denseFont = font === "large" || font === "xlarge";
      if (!denseFont) {
        setSidebarAutoCollapsed(false);
        return;
      }
      const minWidth = font === "xlarge" ? 1700 : 1500;
      setSidebarAutoCollapsed(viewportWidth < minWidth);
    };

    applyAutoCollapse();
    window.addEventListener("resize", applyAutoCollapse);
    const root = document.documentElement;
    const observer = new MutationObserver(applyAutoCollapse);
    observer.observe(root, { attributes: true, attributeFilter: ["data-font"] });
    return () => {
      window.removeEventListener("resize", applyAutoCollapse);
      observer.disconnect();
    };
  }, [setSidebarAutoCollapsed]);
}

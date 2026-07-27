import { createContext, useContext, useEffect, useMemo } from "react";
import { useUrlConfig } from "../hooks/useUrlConfig";
import { useParentEncoderNavigation } from "../hooks/useParentEncoderNavigation";
import { applyDocumentAppConfig } from "./app-config-document.js";
import {
  isAdminConnectRole,
  isOperatorConnectRole,
  isReadOnlyConnectRole,
  normalizeConnectRole,
} from "../utils/rbac.policy.js";

const AppConfigContext = createContext(null);

export function AppConfigProvider({ children }) {
  const { config, patch } = useUrlConfig();

  useEffect(() => {
    applyDocumentAppConfig(config);
  }, [config.theme, config.font, config.role, config.user, config.lang, config.size, config.iframeChild, config.mode]);

  useParentEncoderNavigation(config.iframeChild);

  const value = useMemo(() => {
    const role = normalizeConnectRole(config.role);
    const readOnly = isReadOnlyConnectRole(role);
    return {
      ...config,
      role,
      isAdmin: isAdminConnectRole(role),
      isOperator: isOperatorConnectRole(role),
      isReadOnly: readOnly,
      patch,
    };
  }, [config, patch]);

  return <AppConfigContext.Provider value={value}>{children}</AppConfigContext.Provider>;
}

export function useAppConfig() {
  const ctx = useContext(AppConfigContext);
  if (!ctx) throw new Error("useAppConfig must be used within AppConfigProvider");
  return ctx;
}

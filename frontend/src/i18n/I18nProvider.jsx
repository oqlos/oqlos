import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { dictionaries, resolveKey, SUPPORTED_LANGS } from "./dictionaries.js";

const I18nContext = createContext();

function getInitialLang(forced) {
  if (forced && dictionaries[forced]) return forced;
  const browser = typeof navigator !== "undefined" ? navigator.language?.slice(0, 2) : null;
  return dictionaries[browser] ? browser : "pl";
}

/**
 * @param {object} props
 * @param {React.ReactNode} props.children
 * @param {string} [props.lang] When provided (e.g. from the URL ?lang= param),
 *                              overrides browser-language detection.
 */
export function I18nProvider({ children, lang: forcedLang }) {
  const [lang, setLangState] = useState(() => getInitialLang(forcedLang));

  useEffect(() => {
    if (forcedLang && dictionaries[forcedLang] && forcedLang !== lang) {
      setLangState(forcedLang);
    }
  }, [forcedLang, lang]);

  const setLang = useCallback((l) => {
    if (dictionaries[l]) setLangState(l);
  }, []);

  const dict = dictionaries[lang] || dictionaries.en;

  const t = useCallback(
    (key, varsOrDefault) => {
      let val = resolveKey(dict, key);
      if (val === undefined) {
        // Fallback chain: requested lang → EN → positional default → key string.
        // The positional default lets call sites such as
        //   t("device.selected", "Device")
        // render a meaningful string even when no dictionary entry exists yet.
        val = resolveKey(dictionaries.en, key);
      }
      if (val === undefined) {
        return typeof varsOrDefault === "string" ? varsOrDefault : key;
      }
      if (typeof val === "string" && varsOrDefault && typeof varsOrDefault === "object") {
        return val.replace(/\{(\w+)\}/g, (_, k) => varsOrDefault[k] ?? `{${k}}`);
      }
      return val;
    },
    [dict],
  );

  return (
    <I18nContext.Provider value={{ lang, setLang, t, SUPPORTED_LANGS }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

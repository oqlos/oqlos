/**
 * App-level i18n wiring. Provider implementation lives in
 * `@semcod/frontend-services/i18n.js`; dictionaries stay app-specific
 * (OqlOS has extra hardware translation modules).
 */
import { createI18n } from "@semcod/frontend-services/i18n.js";
import { dictionaries, resolveKey, SUPPORTED_LANGS } from "./dictionaries.js";

export const { I18nProvider, useI18n } = createI18n({
  dictionaries,
  resolveKey,
  supportedLangs: SUPPORTED_LANGS,
  defaultLang: "pl",
});

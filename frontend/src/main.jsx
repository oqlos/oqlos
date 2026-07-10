import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { I18nProvider } from "./i18n/I18nProvider";
import { AppConfigProvider, useAppConfig } from "./context/AppConfigProvider";
import "./styles/global.css";

import { hydrateUiPrefsFromServer } from "./utils/ui-prefs-client.js";
import { hydrateUrlFromUiArgsCookie } from "./utils/ui-url-args-cookie.js";

void hydrateUiPrefsFromServer();
hydrateUrlFromUiArgsCookie();

// Standalone OqlOS hardware UI.

// Thin bridge so I18nProvider picks up the lang from AppConfigProvider.
function LocalizedApp() {
  const { lang } = useAppConfig();
  return (
    <I18nProvider lang={lang}>
      <App />
    </I18nProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter basename="/ui">
      <AppConfigProvider>
        <LocalizedApp />
      </AppConfigProvider>
    </BrowserRouter>
  </React.StrictMode>
);

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { I18nProvider } from "./i18n/I18nProvider";
import { AppConfigProvider, useAppConfig } from "./context/AppConfigProvider";
import "./styles/global.css";

// Standalone OqlOS hardware UI. No iframe-child protocol / scanner bridge (those
// belonged to the c2004 app shell); hardware actuation goes through /api/v3/hardware/*.

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

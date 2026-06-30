// Melody titles + activity log strings (6 langs)
export const hardwareDemoExtraByLang = {
  "pl": {
    "melody": {
      "twinkle": "Gwiazdka świeciła (Twinkle)",
      "ode_to_joy": "Oda do radości (Beethoven)",
      "wlazl_kotek": "Wlazł kotek na płotek",
      "scale": "Skala C-dur (do-re-mi)"
    },
    "log": {
      "pageOpened": "Otwarto demo sprzętu",
      "pageOpenedDetail": "Domyślnie pompa. Przełącz na stepper, jeśli pompa niedostępna.",
      "webAudioUnavailable": "Web Audio niedostępne",
      "webAudioDetail": "Przeglądarka blokuje AudioContext.",
      "pumpProbeFailed": "Test pompy nie powiódł się",
      "pumpStatusLine": "Pompa: {pump} | Stepper: {stepper}",
      "pumpConnectedDetail": "Pompa podłączona — używana domyślnie.",
      "pumpFallbackDetail": "Pompa niedostępna — przełączono na stepper Tic T249.",
      "neitherDeviceDetail": "Brak urządzeń — demo działa tylko przez Web Audio.",
      "identifyFailed": "Identify nie powiódł się",
      "commandFailed": "Polecenie {command} nie powiodło się",
      "pumpAutoSwitch": "Pompa — przełączam na stepper, ponów {command}",
      "stepperFallbackOk": "Stepper (fallback) OK",
      "stepperFallbackFail": "Stepper (fallback) też nie działa",
      "playNote": "Graj {name} → {short}",
      "playingMelody": "Odtwarzam: {title}",
      "playingMelodyDetail": "{count} nut na {short}",
      "melodyStopped": "Melodia przerwana",
      "melodyStoppedDetail": "nuty {at}/{total}",
      "finishedMelody": "Zakończono: {title}"
    }
  },
  "en": {
    "melody": {
      "twinkle": "Twinkle Twinkle Little Star",
      "ode_to_joy": "Ode to Joy (Beethoven)",
      "wlazl_kotek": "The cat on the fence (Polish folk)",
      "scale": "C-Major scale (do-re-mi)"
    },
    "log": {
      "pageOpened": "Hardware demo page opened",
      "pageOpenedDetail": "Pump is default. Switch to stepper if pump unavailable.",
      "webAudioUnavailable": "Web Audio not available",
      "webAudioDetail": "Browser blocks AudioContext.",
      "pumpProbeFailed": "Pump probe failed",
      "pumpStatusLine": "Pump: {pump} | Stepper: {stepper}",
      "pumpConnectedDetail": "Pump connected — using pump as default.",
      "pumpFallbackDetail": "Pump unavailable — auto-switching to stepper Tic T249.",
      "neitherDeviceDetail": "Neither device reachable — Web Audio still works.",
      "identifyFailed": "Identify failed",
      "commandFailed": "{command} failed",
      "pumpAutoSwitch": "Pump failed — auto-switching to stepper, retry {command}",
      "stepperFallbackOk": "Stepper fallback succeeded",
      "stepperFallbackFail": "Stepper fallback also failed",
      "playNote": "Play {name} → {short}",
      "playingMelody": "Playing: {title}",
      "playingMelodyDetail": "{count} notes on {short}",
      "melodyStopped": "Melody stopped",
      "melodyStoppedDetail": "at note {at}/{total}",
      "finishedMelody": "Finished: {title}"
    }
  },
  "de": {
    "melody": {
      "twinkle": "Funkeln, funkeln, kleiner Stern",
      "ode_to_joy": "Ode an die Freude (Beethoven)",
      "wlazl_kotek": "Katze auf dem Zaun (Polnisch)",
      "scale": "C-Dur Tonleiter"
    },
    "log": {
      "pageOpened": "Hardware-Demo geöffnet",
      "pageOpenedDetail": "Pumpe ist Standard. Bei Ausfall Stepper wählen.",
      "webAudioUnavailable": "Web Audio nicht verfügbar",
      "webAudioDetail": "Browser blockiert AudioContext.",
      "pumpProbeFailed": "Pumpen-Test fehlgeschlagen",
      "pumpStatusLine": "Pumpe: {pump} | Stepper: {stepper}",
      "pumpConnectedDetail": "Pumpe verbunden — Standard.",
      "pumpFallbackDetail": "Pumpe nicht verfügbar — Wechsel zu Stepper.",
      "neitherDeviceDetail": "Keine Geräte — nur Web Audio.",
      "identifyFailed": "Identify fehlgeschlagen",
      "commandFailed": "{command} fehlgeschlagen",
      "pumpAutoSwitch": "Pumpe — Wechsel zu Stepper, {command}",
      "stepperFallbackOk": "Stepper-Fallback OK",
      "stepperFallbackFail": "Stepper-Fallback fehlgeschlagen",
      "playNote": "Spiele {name} → {short}",
      "playingMelody": "Spiele: {title}",
      "playingMelodyDetail": "{count} Noten auf {short}",
      "melodyStopped": "Melodie gestoppt",
      "melodyStoppedDetail": "Note {at}/{total}",
      "finishedMelody": "Fertig: {title}"
    }
  },
  "ru": {
    "melody": {
      "twinkle": "Twinkle Twinkle",
      "ode_to_joy": "Ода к радости (Бетховен)",
      "wlazl_kotek": "Кот на заборе",
      "scale": "Гамма до мажор"
    },
    "log": {
      "pageOpened": "Открыта демо-страница",
      "pageOpenedDetail": "Насос по умолчанию.",
      "webAudioUnavailable": "Web Audio недоступен",
      "webAudioDetail": "Браузер блокирует AudioContext.",
      "pumpProbeFailed": "Проверка насоса не удалась",
      "pumpStatusLine": "Насос: {pump} | Stepper: {stepper}",
      "pumpConnectedDetail": "Насос подключён.",
      "pumpFallbackDetail": "Насос недоступен — переключение на stepper.",
      "neitherDeviceDetail": "Устройства недоступны — только Web Audio.",
      "identifyFailed": "Identify не удался",
      "commandFailed": "{command} ошибка",
      "pumpAutoSwitch": "Насос — переключение на stepper, {command}",
      "stepperFallbackOk": "Stepper fallback OK",
      "stepperFallbackFail": "Stepper fallback не удался",
      "playNote": "Играть {name} → {short}",
      "playingMelody": "Воспроизведение: {title}",
      "playingMelodyDetail": "{count} нот на {short}",
      "melodyStopped": "Мелодия остановлена",
      "melodyStoppedDetail": "нота {at}/{total}",
      "finishedMelody": "Готово: {title}"
    }
  },
  "ua": {
    "melody": {
      "twinkle": "Twinkle Twinkle",
      "ode_to_joy": "Ода до радості (Бетховен)",
      "wlazl_kotek": "Кіт на паркані",
      "scale": "Гама до мажор"
    },
    "log": {
      "pageOpened": "Відкрито демо",
      "pageOpenedDetail": "Насос за замовчуванням.",
      "webAudioUnavailable": "Web Audio недоступний",
      "webAudioDetail": "Браузер блокує AudioContext.",
      "pumpProbeFailed": "Перевірка насоса не вдалася",
      "pumpStatusLine": "Насос: {pump} | Stepper: {stepper}",
      "pumpConnectedDetail": "Насос підключено.",
      "pumpFallbackDetail": "Насос недоступний — stepper.",
      "neitherDeviceDetail": "Пристрої недоступні — лише Web Audio.",
      "identifyFailed": "Identify не вдався",
      "commandFailed": "{command} помилка",
      "pumpAutoSwitch": "Насос — stepper, {command}",
      "stepperFallbackOk": "Stepper fallback OK",
      "stepperFallbackFail": "Stepper fallback не вдався",
      "playNote": "Грати {name} → {short}",
      "playingMelody": "Відтворення: {title}",
      "playingMelodyDetail": "{count} нот на {short}",
      "melodyStopped": "Мелодію зупинено",
      "melodyStoppedDetail": "нота {at}/{total}",
      "finishedMelody": "Завершено: {title}"
    }
  },
  "cs": {
    "melody": {
      "twinkle": "Twinkle Twinkle Little Star",
      "ode_to_joy": "Óda na radost (Beethoven)",
      "wlazl_kotek": "Kočka na plotě",
      "scale": "Stupnice C dur"
    },
    "log": {
      "pageOpened": "Demo hardware otevřeno",
      "pageOpenedDetail": "Výchozí je čerpadlo.",
      "webAudioUnavailable": "Web Audio nedostupné",
      "webAudioDetail": "Prohlížeč blokuje AudioContext.",
      "pumpProbeFailed": "Test čerpadla selhal",
      "pumpStatusLine": "Čerpadlo: {pump} | Stepper: {stepper}",
      "pumpConnectedDetail": "Čerpadlo připojeno.",
      "pumpFallbackDetail": "Čerpadlo nedostupné — stepper.",
      "neitherDeviceDetail": "Zařízení nedostupná — jen Web Audio.",
      "identifyFailed": "Identify selhal",
      "commandFailed": "{command} selhalo",
      "pumpAutoSwitch": "Čerpadlo — stepper, {command}",
      "stepperFallbackOk": "Stepper fallback OK",
      "stepperFallbackFail": "Stepper fallback selhal",
      "playNote": "Hrát {name} → {short}",
      "playingMelody": "Přehrávám: {title}",
      "playingMelodyDetail": "{count} not na {short}",
      "melodyStopped": "Melodie zastavena",
      "melodyStoppedDetail": "nota {at}/{total}",
      "finishedMelody": "Hotovo: {title}"
    }
  }
};

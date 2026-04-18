# =============================================================================
# DSL: Test Szczelności Maski Ochronnej
# Scenariusz: scn-mask-leak-test
# Dotyczy: maski pełnotwarzowe (MSA Ultra Elite, Dräger FPS 7000 i inne)
# =============================================================================

SCENARIO_ID: "scn-mask-leak-test"
DEVICE_KIND:  "pp-mask"

SENSORS:
  AI01: "Czujnik ciśnienia NC (mbar)"    unit: mbar

OUTPUTS:
  Pump:
    - off:  "Pompa wyłączona"
    - 20:   "Pompa 20% — wytwarzanie podciśnienia"
    - 5:    "Pompa 5% — delikatne nadciśnienie"
  Valve:
    - NC:          "Zawór NC (normalnie zamknięty)"
    - overpressure: "Zawór nadciśnienia"

# -----------------------------------------------------------------------------
# GOAL 1: Oględziny wizualne maski
# -----------------------------------------------------------------------------

@MaskLeakTest.OgledinyWizualne
  description: "Sprawdzenie stanu wizualnego maski przed testem"

  1. Kontrola wizualna:
     → Operator.confirm "Sprawdź stan wizualny maski — uszczelki, elementy elastyczne, szyba"
     SAVE: result

  1.1 Montaż na głowę testową:
     → Operator.confirm "Nałóż maskę na głowę testową i dokładnie uszczelnij"

# -----------------------------------------------------------------------------
# GOAL 2: Test szczelności maski (-10 mbar / 60 s)
# -----------------------------------------------------------------------------

@MaskLeakTest.TestSzczelnosci
  description: "Wytworzenie podciśnienia -10 mbar i obserwacja przez 60 sekund"
  editable: true

  2. Wytworzenie podciśnienia:
     → Pump.set 20
     → Valve.NC on
     WAIT 2000 ms
     AI01 ∈ [-11.0, -9.0] mbar          | ERROR "Podciśnienie startowe poza zakresem"
     SAVE: AI01.value

  2.1 Stabilizacja (60 sekund):
     → Pump.off
     Timer = 60 s                        | WAIT
     AI01 ∈ [-11.0, -9.0] mbar          | ERROR "Maska nieszczelna — delta > 1 mbar"
     SAVE: AI01.value

# -----------------------------------------------------------------------------
# GOAL 3: Test ciśnienia otwarcia zaworu wydechowego
# -----------------------------------------------------------------------------

@MaskLeakTest.CisnienieOtwarciaZaworu
  description: "Ciśnienie otwarcia zaworu wydechowego: 4.2 – 6.0 mbar"
  editable: true

  3. Pomiar ciśnienia otwarcia:
     → Pump.set 5
     → Valve.NC off
     WAIT 1000 ms
     AI01 ∈ [4.2, 6.0] mbar             | ERROR "Ciśnienie otwarcia poza zakresem"
     SAVE: AI01.min

# -----------------------------------------------------------------------------
# GOAL 4: Test nadciśnienia statycznego
# -----------------------------------------------------------------------------

@MaskLeakTest.NadcisnienieStatyczne
  description: "Nadciśnienie statyczne w masce: 1.0 – 3.9 mbar"
  editable: true

  4. Pomiar nadciśnienia:
     → Pump.set 5
     → Valve.overpressure on
     WAIT 3000 ms
     AI01 ∈ [1.0, 3.9] mbar             | ERROR "Nadciśnienie statyczne poza zakresem"
     SAVE: AI01.value

# =============================================================================
# METADATA
# =============================================================================

META:
  standard:    "EN 136 / EN 137"
  device_kind: "Maska pełnotwarzowa"
  ai_sensor:   "AI01 — czujnik ciśnienia NC [mbar]"

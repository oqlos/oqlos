# =============================================================================
# DSL: Maska nadciśnieniowa — DRAGER FPS 7000
# Wygenerowano z: dv00003/tst00000
# Data: 2020.03.03 08:26:10
# Klient: _MASK SERVICE, Gdynia
# =============================================================================

DEVICE_TYPE: "Maska nadciśnieniowa"
DEVICE_MODEL: "DRAGER FPS 7000"
MANUFACTURER: "DRAGER A.G."

INTERVALS:
  - tt#000: "Co 1/2 roku"   period: 6 months
  - tt#001: "Co 1 rok"   period: 12 months
  - tt#002: "Po użyciu"   period: 0 months
  - tt#003: "Co 5 lat"   period: 60 months
  - tt#005: "Co 6 lat"   period: 72 months

# -----------------------------------------------------------------------------
# SCENARIUSZ: Pełny test maski
# -----------------------------------------------------------------------------

@DRAGERFPS7000.Pełnytestmaski
  description: "Pełny test maski"
  intervals: [tt#000, tt#001, tt#002, tt#003, tt#005]

  # === GOAL 1: TEST WIZUALNY ===
  TESTWIZUALNY:

    1. TEST WIZUALNY:
       → Pump.off
       → Operator.confirm "Test wizualny"
       SAVE: operator.result

    1.1. Doszczelnienie głowy testowej:
       → BO02.on
       → Pump.set 5l
       # Czas pompowania głowy [s]
       Timer ≤ 7.0 s                     | WAIT

    1.2. Wytworzenie podciśnienia NC:
       → BO06.on
       → Pump.set 5l
       AI01 ≥ -11.0 mbar             | PASS "Wytworzenie  podciśnienia [mbar]"
       # Przekroczenie czasu [s]
       Timer ≤ 10.0 s                     | ERROR "Przekroczenie czasu [s]"

    1.3. Stabilizacja ciśnienia:
       → Pump.off
       # Stabilizacja ciśnienia [s]
       Timer ≤ 10.0 s                     | WAIT

    1.4. Ustawienie parametru Auto:
       → BO04.on
       → Pump.off
       AI01 ≤ -10.1 mbar             | PASS "Ustawienie parametru Auto [s]"
       # Czas ustawienia [s]
       Timer ≤ 20.0 s                     | ERROR "Czas ustawienia [s]"

  # === GOAL 2: TEST SZCZELNOŚCI MASKI NADCIŚNIENIOWEJ ===
  TESTSZCZELNOŚCIMASKINADCIŚNIENIOWEJ:
    alarm: "Wykryto nieszczelność"

    2. TEST SZCZELNOŚCI MASKI NADCIŚNIENIOWEJ:
       → Pump.off
       AI01 ≤ -9.0 mbar              | ERROR "Test szczelności maski"
       SAVE: AI01.value
       # Czas badania [s]
       Timer ≤ 60.0 s                     | WAIT

    2.1. Ciśnienie otwarcia zaworu wydechowego:
       → BO05.on
       → Pump.set 10l
       Timer ≤ 5.0 s                     | WAIT

    2.2. CIŚNIENIE OTWARCIA ZAWORU WYDECHOWEGO:
       → BO05.on
       → Pump.set 10l
       AI01 ∈ [4.2, 6.0] mbar        | PASS "Ciśnienie otwarcia zaworu wydechowego"
       SAVE: AI01.value
       Timer ≤ 1.0 s                     | ERROR ""

    2.3. Odpowietrzenie głowy testowej:
       → BO03.on
       → Pump.set 5l
       Timer ≤ 7.0 s                     | WAIT

SENSORS:
  AI01: "Czujnik ciśnienia"   unit: mbar
  AI01: "Czujnik ciśnienia"   unit: mbar
  AI02: "Czujnik ciśnienia"   unit: mbar
  AI03: "Czujnik ciśnienia"   unit: mbar

# =============================================================================
META:
  source: "dv00003/tst00000"
  device_id: "dv00003"
  device_number: "FPS_001"
  barcode: "AN398"
  customer: "_MASK SERVICE"
  location: "Gdynia, Góralska 12"
  test_date: "2020.03.03 08:26:10"
  result: "OK"

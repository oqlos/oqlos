SCENARIO: "Technical Medical Script"
DEVICE_TYPE: "Simulator"

GOAL: Test wizualny aparatu
  VAL 'wynik' 'OK/NOK'
  SAVE 'wynik'

GOAL: Odkryj zawór butli
  SET 'zawór butli 300 bar' '1 (open)'

GOAL: Test statyczny średniego ciśnienia
  SET 'PUMP' '0 l/min (off)'
  SET 'timeout' '3 s'
  SET 'timer' '0 s'
  
  # This IF should skip the rest if timer <= timeout (which is true at start)
  # But in flat DSL, we often use IF as a 'gate'.
  IF 'timer' > 'timeout'
    MIN 'ciśnienie SC' '6.0 bar'
    MAX 'ciśnienie SC' '8.0 bar'
    VAL 'ciśnienie SC' 'bar'
    SAVE 'ciśnienie SC'
  ENDIF

GOAL: Test szczelności układu WC
  SET 'PUMP' '0 l/min (off)'
  SET 'czas obserwacji' '5 s'
  SET 'timer' '0 s'
  WAIT '1.0 s'

GOAL: Test nadciśnienia statycznego
  SET 'PUMP' '0 l/min (off)'
  SET 'timeout' '5 s'
  SET 'timer' '0 s'
  # Condition met in simulation to execute the following
  SET 'timer' '10 s'
  IF 'timer' > 'timeout'
    MIN 'nadciśnienie' '2.2 mbar'
    MAX 'nadciśnienie' '4.1 mbar'
    VAL 'nadciśnienie' 'mbar'
    SAVE 'nadciśnienie'
  ENDIF

GOAL: Test sygnału akustycznego
  SET 'PUMP' '5.0 l/min'
  SET 'zawór BO06' '1 (open)'
  MIN 'ciśnienie NC' '0.0 mbar'
  VAL 'ciśnienie NC' 'mbar'
  SAVE 'wynik sygnału'

GOAL: Asercja inline
  IF 'AI01' < '10.0 mbar' ELSE ERROR 'Custom failure message'

SCENARIO: 'Dräger FPS 7000 Full Test'
DEVICE_TYPE: 'BA'
DEVICE_MODEL: 'FPS 7000'
MANUFACTURER: 'Dräger'

GOAL: Pełny test maski
  SET 'pompa 1' '0 l/min'
  SET 'Operator' 'confirm'
  SAVE 'operator.result'
  
  SET 'valve-sc' '1'
  SET 'pompa 1' '5.0 l/min'
  
  IF 'Timer' ≤ '7.0 s'
    SET 'valve-nc' '1'
    SET 'pompa 1' '5.0 l/min'
    
    IF 'AI01' ≥ '-11.0 mbar'
      IF 'Timer' ≤ '15.0 s'
        SET 'pompa 1' '0 l/min'
        VAL 'Cisnienie NC' 'AI01'
        SAVE 'AI01.value'
        
        IF 'AI01' ≤ '-9.0 mbar'
          # Koniec ścieżki
        ENDIF
      ENDIF
    ENDIF
  ENDIF

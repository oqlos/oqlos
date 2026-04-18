SCENARIO: "Test Block IF"
DEVICE_TYPE: "Simulator"

GOAL: Verify conditional branching
    # Check branch selection
    # Dry-run default for AI01 is -12.0
    IF 'AI01' < '0.0'
        SET 'Valve' '1 (open)'
        SET 'Pump' '50 l/min'
    ELSE
        SET 'Valve' '0 (close)'
        SET 'Pump' '0 l/min'
    ENDIF
    
    # This IF should go to ELSE branch if we nudge AI01 or use simple case
    IF 'AI01' > '0.0'
        SET 'Pump' '100 l/min'
    ELSE
        SET 'Pump' '10 l/min'
    ENDIF

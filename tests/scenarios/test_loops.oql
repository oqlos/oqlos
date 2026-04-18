SCENARIO: "Test DSL Loops"
DEVICE_TYPE: "Simulator"

GOAL: Verify loop execution
    # Counted loop
    VAR counter = "0"
    LOOP 3 TIMES
        SET 'Pump' '10 l/min'
        # Wait or other actions
    ENDLOOP
    
    # Conditional loop
    # Dry-run condition simulation
    LOOP WHILE 'AI01' < '0.0 mbar'
        SET 'Valve' '1 (open)'
        WAIT '1.0 s'
    ENDLOOP

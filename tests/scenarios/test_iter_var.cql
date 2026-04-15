SCENARIO: "Test Iter Variable"
DEVICE_TYPE: "Simulator"

GOAL: Verify ITER increments
    # Print ITER
    LOOP 3 TIMES
        WAIT '100 ms'
        # ITER is automatically injected by loop handler
    ENDLOOP

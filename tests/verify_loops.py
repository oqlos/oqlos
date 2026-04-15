import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from oqlos.core.interpreter import CqlInterpreter
from oqlos.core.base import StepStatus

def test_loops():
    print("Testing Block LOOP/ENDLOOP...")
    
    scenario_path = os.path.join(os.path.dirname(__file__), 'scenarios', 'test_loops.cql')
    with open(scenario_path, 'r') as f:
        source = f.read()
    
    interpreter = CqlInterpreter(mode="dry-run")
    parsed = interpreter.parse(source, "test_loops.cql")
    result = interpreter.execute(parsed)
    
    print(f"\nResult: {'SUCCESS' if result.ok else 'FAILURE'}")
    
    assert result.ok, "Execution failed"
    print("\n✅ Block LOOP execution logic verified via dry-run logs.")

if __name__ == "__main__":
    try:
        test_loops()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

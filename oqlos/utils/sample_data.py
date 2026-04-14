# firmware/utils/sample_data.py
from oqlos.models.scenario import Scenario, Goal, Step, ValidationRule
from oqlos.core.state import StateManager

def load_sample_scenarios(state_manager: StateManager):
    """Load sample scenarios for testing"""
    mask_leak_test = Scenario(
        id='scn-mask-leak-test',
        name='Mask Leak Test',
        description='Test mask seal integrity under pressure',
        device='mask-pp-g1',
        protocol='pr-e999e1e0',
        goals=[
            Goal(
                id='goal-1',
                name='Prepare System',
                description='Set system to initial state',
                steps=[
                    Step(id='s1', action='SET_VALVE', peripheral='valve-1', value=False),
                    Step(id='s2', action='SET_VALVE', peripheral='valve-nc', value=True),
                    Step(id='s3', action='SET_PUMP', peripheral='pump-main', value=0),
                    Step(id='s4', action='WAIT', duration=1000)
                ],
                expectedResult='All valves closed except NC, pump off',
                validationCriteria=[
                    ValidationRule(
                        peripheral='nc-sensor',
                        condition='value >= -1 and value <= 1',
                        errorMessage='NC pressure not zero'
                    )
                ]
            ),
            Goal(
                id='goal-2',
                name='Apply Negative Pressure',
                description='Create -20 mbar pressure in NC circuit',
                steps=[
                    Step(id='s1', action='SET_PUMP', peripheral='pump-main', value=30),
                    Step(id='s2', action='WAIT', duration=2000),
                    Step(id='s3', action='read_SENSOR', peripheral='nc-sensor'),
                    Step(id='s4', action='VALIDATE', condition='nc-sensor.currentValue >= -22 and nc-sensor.currentValue <= -18')
                ],
                expectedResult='NC pressure stabilized at -20 mbar',
                validationCriteria=[
                    ValidationRule(
                        peripheral='nc-sensor',
                        condition='value >= -22 and value <= -18',
                        errorMessage='NC pressure out of range'
                    )
                ]
            ),
            Goal(
                id='goal-3',
                name='Monitor Leak Rate',
                description='Measure pressure change over 30 seconds',
                steps=[
                    Step(id='s1', action='SET_PUMP', peripheral='pump-main', value=0),
                    Step(id='s2', action='WAIT', duration=5000),  # Shortened for demo
                    Step(id='s3', action='READ_SENSOR', peripheral='nc-sensor')
                ],
                expectedResult='Leak rate < 5 mbar/min',
                validationCriteria=[
                    ValidationRule(
                        peripheral='nc-sensor',
                        condition='value >= -23 and value <= -17',
                        errorMessage='Leak rate too high'
                    )
                ]
            )
        ]
    )
    
    state_manager.scenarios[mask_leak_test.id] = mask_leak_test

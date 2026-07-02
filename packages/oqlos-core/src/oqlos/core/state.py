# firmware/services/state_manager.py
from fastapi import WebSocket

try:
    from nfo import logged
except ImportError:
    def logged(cls=None, **kw):
        return cls if cls is not None else (lambda c: c)

from oqlos.models.peripheral import Peripheral, PeripheralType, PeripheralStatus, PeripheralMode
from oqlos.models.scenario import Scenario
from oqlos.models.execution import ExecutionStatus

@logged
class StateManager:
    def __init__(self):
        self.peripherals: dict[str, Peripheral] = {}
        self.executions: dict[str, ExecutionStatus] = {}
        self.scenarios: dict[str, Scenario] = {}
        self.websocket_connections: list[WebSocket] = []
        self.initialize_peripherals()
        
    def initialize_peripherals(self):
        """Initialize all peripheral devices"""
        # Pressure Sensors
        self.peripherals['nc-sensor'] = Peripheral(
            id='nc-sensor',
            type=PeripheralType.PRESSURE_SENSOR,
            name='NC Sensor (Low Pressure)',
            currentValue=0,
            targetValue=0,
            unit='mbar',
            range={'min': -60, 'max': 60},
            status=PeripheralStatus.OK,
            mode=PeripheralMode.AUTO,
            dependencies=['valve-nc', 'pump-main']
        )
        
        self.peripherals['sc-sensor'] = Peripheral(
            id='sc-sensor',
            type=PeripheralType.PRESSURE_SENSOR,
            name='SC Sensor (Medium Pressure)',
            currentValue=0,
            targetValue=0,
            unit='bar',
            range={'min': 0, 'max': 25},
            status=PeripheralStatus.OK,
            mode=PeripheralMode.AUTO,
            dependencies=['valve-sc', 'pump-main']
        )
        
        self.peripherals['wc-sensor'] = Peripheral(
            id='wc-sensor',
            type=PeripheralType.PRESSURE_SENSOR,
            name='WC Sensor (High Pressure)',
            currentValue=0,
            targetValue=0,
            unit='bar',
            range={'min': 0, 'max': 400},
            status=PeripheralStatus.OK,
            mode=PeripheralMode.AUTO,
            dependencies=['valve-wc', 'pump-main']
        )
        
        # Valves (numbered 1-14)
        for i in range(1, 15):
            self.peripherals[f'valve-{i}'] = Peripheral(
                id=f'valve-{i}',
                type=PeripheralType.VALVE,
                name=f'Valve #{i}',
                currentValue=False,
                targetValue=False,
                status=PeripheralStatus.OK,
                mode=PeripheralMode.AUTO
            )
        
        # Special circuit valves
        for circuit in ['nc', 'sc', 'wc']:
            self.peripherals[f'valve-{circuit}'] = Peripheral(
                id=f'valve-{circuit}',
                type=PeripheralType.VALVE,
                name=f'{circuit.upper()} Circuit Valve',
                currentValue=False,
                targetValue=False,
                status=PeripheralStatus.OK,
                mode=PeripheralMode.AUTO
            )
        
        # Main Pump
        self.peripherals['pump-main'] = Peripheral(
            id='pump-main',
            type=PeripheralType.PUMP,
            name='Main Pump',
            currentValue=0,
            targetValue=0,
            unit='%',
            range={'min': 0, 'max': 100},
            status=PeripheralStatus.OK,
            mode=PeripheralMode.AUTO
        )
        
        # Artificial Lung
        self.peripherals['lung-main'] = Peripheral(
            id='lung-main',
            type=PeripheralType.ARTIFICIAL_LUNG,
            name='Artificial Lung',
            currentValue={'volume': 0, 'pressure': 0},
            targetValue={'volume': 0, 'pressure': 0},
            status=PeripheralStatus.OK,
            mode=PeripheralMode.AUTO,
            dependencies=['nc-sensor', 'valve-1']
        )
    
    async def broadcast_event(self, event: dict):
        """Broadcast event to all connected WebSocket clients"""
        disconnected = []
        for ws in self.websocket_connections:
            try:
                await ws.send_json(event)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.websocket_connections.remove(ws)

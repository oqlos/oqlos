# firmware/services/scenario_orchestrator.py
import asyncio
import ast
import logging
from datetime import datetime, timezone
from typing import Any

from oqlos.core._compare import resolve_compare_chain


def _resolve_compare(node: ast.Compare, context: dict[str, Any]) -> bool:
    """Resolve a Compare node (a < b, chained comparisons)."""
    return resolve_compare_chain(node, lambda current: _safe_resolve(current, context))


def _resolve_name_or_attr(node: Any, context: dict[str, Any]) -> Any:
    """Resolve Name or Attribute nodes against context."""
    if isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        raise ValueError(f"Unknown variable: {node.id}")
    # ast.Attribute
    obj = _safe_resolve(node.value, context)
    if hasattr(obj, node.attr):
        return getattr(obj, node.attr)
    raise ValueError(f"Object has no attribute '{node.attr}'")


def _safe_resolve(node: Any, context: dict[str, Any]) -> Any:
    """Resolve a single AST node against *context*."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, bool)):
        return node.value
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, (ast.USub, ast.UAdd)):
            operand = _safe_resolve(node.operand, context)
            return -operand if isinstance(node.op, ast.USub) else operand
        if isinstance(node.op, ast.Not):
            return not _safe_resolve(node.operand, context)
    if isinstance(node, (ast.Name, ast.Attribute)):
        return _resolve_name_or_attr(node, context)
    if isinstance(node, ast.Compare):
        return _resolve_compare(node, context)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_safe_resolve(v, context) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_safe_resolve(v, context) for v in node.values)
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def safe_eval_condition(expr: str, context: dict[str, Any]) -> bool:
    """Evaluate a simple comparison expression without using eval().

    Supports:
      - Numeric literals and negative numbers
      - Bare names and dotted attribute access resolved against *context*
      - Comparisons: <, <=, >, >=, ==, !=
      - Boolean operators: and, or, not

    Raises ValueError for unsupported syntax.
    """
    try:
        tree = ast.parse(expr.strip(), mode='eval')
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}") from e

    return bool(_safe_resolve(tree.body, context))

logger = logging.getLogger(__name__)

from oqlos.models.scenario import Step, Goal
from oqlos.models.execution import ExecutionStatus
from oqlos.core.state import StateManager, logged
from oqlos.core.cqrs.execution import (
    SetExecutionStatusCommand,
    StartExecutionCommand,
    StartGoalCommand,
    StartStepCommand,
    UpdateProgressCommand,
)
from oqlos.core.cqrs.peripheral import SetPeripheralValueCommand
from oqlos.hardware.plugin_gateway import PluginHardwareGateway

@logged
class ScenarioOrchestrator:
    def __init__(self, state_manager: StateManager, hardware: PluginHardwareGateway | None = None):
        self.state_manager = state_manager
        self.hardware = hardware or PluginHardwareGateway()
        self.running = False
        self.paused = False
        self.current_execution_id: str | None = None
        self.current_index: int = -1
        self._step_plan: list[Step] = []

    @property
    def current_execution(self) -> ExecutionStatus | None:
        """Always resolved fresh from the event-sourced projection — never a stale reference."""
        if self.current_execution_id is None:
            return None
        return self.state_manager.executions.get(self.current_execution_id)
    
    def _sanitize_identifier(self, name: str) -> str:
        """Convert peripheral IDs like 'nc-sensor'/'pump-main' to python-safe identifiers."""
        return name.replace('-', '_').replace('.', '_').replace(' ', '_')

    def _build_eval_context(self) -> dict[str, Any]:
        """Expose peripherals in eval context using sanitized identifiers."""
        ctx: dict[str, Any] = {}
        for pid, per in self.state_manager.peripherals.items():
            ctx[self._sanitize_identifier(pid)] = per
        # Convenience aliases (optional)
        if 'nc-sensor' in self.state_manager.peripherals:
            ctx['nc_sensor'] = self.state_manager.peripherals['nc-sensor']
        if 'sc-sensor' in self.state_manager.peripherals:
            ctx['sc_sensor'] = self.state_manager.peripherals['sc-sensor']
        if 'wc-sensor' in self.state_manager.peripherals:
            ctx['wc_sensor'] = self.state_manager.peripherals['wc-sensor']
        return ctx

    def _sanitize_expression(self, expr: str) -> str:
        if not expr:
            return expr
        sanitized = expr
        for pid in self.state_manager.peripherals.keys():
            sanitized = sanitized.replace(pid, self._sanitize_identifier(pid))
        return sanitized
        
    def _build_step_plan(self, goals_to_run: list) -> None:
        """Flatten goal steps into a linear plan for projection tracking."""
        self._step_plan = []
        self._step_counter = 0
        for g in goals_to_run:
            for st in (g.steps or []):
                self._step_plan.append(st)
        self.current_index = -1

    async def _execute_goal_steps(
        self, goal, execution_id: str,
        mode: str, speed: float, total_steps: int, completed_steps: int
    ) -> int:
        """Run all steps in a single goal, returning updated completed_steps count."""
        bus = self.state_manager.command_bus
        for step in goal.steps:
            if not self.running:
                break
            while self.paused:
                await asyncio.sleep(0.1)

            bus.dispatch(StartStepCommand(execution_id=execution_id, step_id=step.id))
            self.current_index = self._step_counter
            self._step_counter += 1

            human = getattr(step, 'label', None)
            if not human:
                human = f"{step.action}" + (f" [{step.peripheral}]" if step.peripheral else "")
            await self.log_event('info', f"⏳ Executing: {human}")
            await self.execute_step(step, mode, speed)

            completed_steps += 1
            bus.dispatch(UpdateProgressCommand(
                execution_id=execution_id, progress=(completed_steps / total_steps) * 100
            ))

            execution = self.state_manager.executions[execution_id]
            await self.state_manager.broadcast_event({
                'type': 'execution_update',
                'executionId': execution_id,
                'currentIndex': self.current_index,
                'status': execution.status,
                'currentGoal': execution.currentGoal,
                'currentStep': execution.currentStep,
                'progress': execution.progress
            })
        return completed_steps

    async def execute_scenario(self, scenario_id: str, goals: list[str] | None, mode: str, speed: float):
        """Execute a scenario with specified goals"""
        scenario = self.state_manager.scenarios.get(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        execution_id = f"exec-{datetime.now(timezone.utc).timestamp()}"
        bus = self.state_manager.command_bus
        bus.dispatch(StartExecutionCommand(execution_id=execution_id, scenario_id=scenario_id))

        self.current_execution_id = execution_id
        self.running = True

        # Filter goals if specified
        goals_to_run = scenario.goals
        if goals:
            goals_to_run = [g for g in scenario.goals if g.id in goals]

        total_steps = sum(len(g.steps) for g in goals_to_run)
        completed_steps = 0
        self._build_step_plan(goals_to_run)

        for goal in goals_to_run:
            if not self.running:
                break
            bus.dispatch(StartGoalCommand(execution_id=execution_id, goal_id=goal.id))
            await self.log_event('info', f'Starting GOAL: {goal.name}')

            completed_steps = await self._execute_goal_steps(
                goal, execution_id, mode, speed, total_steps, completed_steps
            )

            validation_passed = await self.validate_goal(goal)
            if validation_passed:
                await self.log_event('success', f'✓ GOAL completed successfully')
            else:
                await self.log_event('error', f'✗ GOAL validation failed')

        bus.dispatch(SetExecutionStatusCommand(execution_id=execution_id, status='completed'))
        self.running = False
        if self._step_plan:
            self.current_index = len(self._step_plan) - 1
        return execution_id
    
    async def execute_step(self, step: Step, mode: str, speed: float):
        """Execute a single step"""
        await self.log_event('info', f'⚙️ Executing step {step.id}: {step.action}')
        if step.peripheral:
            await self.log_event('info', f'🎛️ Target peripheral: {step.peripheral}')
        
        # Add small delay to make execution visible
        await asyncio.sleep(0.5 / speed if speed > 0 else 0.5)
        
        act = (step.action or '').upper()
        if act == 'SET_VALVE':
            await self._execute_valve_step(step, mode)
                
        elif act == 'SET_PUMP':
            await self._execute_pump_step(step, mode, speed)
        
        elif act == 'WAIT':
            await self._execute_wait_step(step, speed)
        
        elif act == 'READ_SENSOR':
            await self._execute_sensor_read_step(step)
        
        elif act == 'SET_LUNG':
            await self._execute_lung_step(step, mode)
        
        elif act == 'VALIDATE':
            await self._execute_validate_step(step)

    async def _execute_lung_step(self, step: Step, mode: str):
        """Execute artificial lung reciprocating motion step."""
        cycles = int(step.value) if step.value and step.value > 0 else 5
        if mode == 'auto':
            await self.log_event('info', f'🫁 Lung reciprocate: {cycles} cycles')
            if step.value == 0:
                await self.hardware.stop_lung()
            else:
                await self.hardware.set_lung(cycles=cycles)

    async def _execute_valve_step(self, step: Step, mode: str):
        """Execute valve control step"""
        if step.peripheral and step.peripheral in self.state_manager.peripherals:
            peripheral = self.state_manager.peripherals[step.peripheral]
            if mode == 'auto' or peripheral.mode == 'auto':
                self.state_manager.command_bus.dispatch(SetPeripheralValueCommand(
                    peripheral_id=step.peripheral, current_value=step.value, target_value=step.value,
                ))
                await self.log_event('info', f'{peripheral.name}: {"OPEN" if step.value else "CLOSED"}')
                await self.hardware.set_valve(step.peripheral, bool(step.value))

    async def _execute_pump_step(self, step: Step, mode: str, speed: float):
        """Execute pump control step"""
        if step.peripheral and step.peripheral in self.state_manager.peripherals:
            peripheral = self.state_manager.peripherals[step.peripheral]
            if mode == 'auto' or peripheral.mode == 'auto':
                # Simulate gradual pump power change
                bus = self.state_manager.command_bus
                start_value = peripheral.currentValue
                target_value = step.value
                steps = 10
                for i in range(steps):
                    current_value = start_value + (target_value - start_value) * (i + 1) / steps
                    bus.dispatch(SetPeripheralValueCommand(
                        peripheral_id=step.peripheral, current_value=current_value, target_value=peripheral.targetValue,
                    ))
                    await self.update_dependent_sensors(step.peripheral)
                    await asyncio.sleep(0.1 / speed)
                bus.dispatch(SetPeripheralValueCommand(
                    peripheral_id=step.peripheral, current_value=target_value, target_value=target_value,
                ))
                await self.log_event('info', f'Pump power: {target_value}%')
                await self.hardware.set_pump(float(target_value))

    async def _execute_wait_step(self, step: Step, speed: float):
        """Execute wait step"""
        if step.duration:
            await asyncio.sleep(step.duration / 1000 / speed)

    async def _execute_sensor_read_step(self, step: Step):
        """Execute sensor reading step"""
        if step.peripheral and step.peripheral in self.state_manager.peripherals:
            peripheral = self.state_manager.peripherals[step.peripheral]
            hw_value = await self.hardware.read_sensor(step.peripheral)
            if hw_value is not None:
                self.state_manager.command_bus.dispatch(SetPeripheralValueCommand(
                    peripheral_id=step.peripheral, current_value=hw_value, target_value=peripheral.targetValue,
                ))
                peripheral = self.state_manager.peripherals[step.peripheral]
            await self.log_event('info', f'{peripheral.name} reading: {peripheral.currentValue} {peripheral.unit}')

    async def _execute_validate_step(self, step: Step):
        """Execute validation step"""
        if step.condition:
            try:
                expr = self._sanitize_expression(step.condition)
                ctx = self._build_eval_context()
                # Provide convenient alias for current value when peripheral specified
                try:
                    if step.peripheral and step.peripheral in self.state_manager.peripherals:
                        ctx['value'] = self.state_manager.peripherals[step.peripheral].currentValue
                except Exception as e:  # noqa: BLE001
                    logger.debug("Could not resolve peripheral value alias: %s", e)
                result = safe_eval_condition(expr, ctx)
                if result:
                    await self.log_event('success', f'✓ Validation PASSED: {step.condition}')
                else:
                    await self.log_event('error', f'✗ Validation FAILED: {step.condition}')
            except Exception as ex:
                # Do not crash the whole execution; log and continue
                await self.log_event('error', f'Failed to evaluate validation: {step.condition} ({ex})')
    
    async def update_dependent_sensors(self, pump_id: str):
        """Update sensor values based on pump and valve states"""
        # Simplified physics simulation
        bus = self.state_manager.command_bus
        pump_power = self.state_manager.peripherals[pump_id].currentValue

        # Update NC sensor if valve is open
        valve_nc = self.state_manager.peripherals.get('valve-nc')
        if valve_nc and valve_nc.currentValue:
            nc_sensor = self.state_manager.peripherals.get('nc-sensor')
            if nc_sensor:
                # Negative pressure proportional to pump power
                value = -pump_power * 0.6  # -60 mbar at 100% power
                bus.dispatch(SetPeripheralValueCommand(
                    peripheral_id='nc-sensor', current_value=value, target_value=nc_sensor.targetValue,
                ))
                await self.log_event('info', f'NC Sensor: {value:.1f} mbar')

        # Update SC sensor if valve is open
        valve_sc = self.state_manager.peripherals.get('valve-sc')
        if valve_sc and valve_sc.currentValue:
            sc_sensor = self.state_manager.peripherals.get('sc-sensor')
            if sc_sensor:
                value = pump_power * 0.25  # 25 bar at 100% power
                bus.dispatch(SetPeripheralValueCommand(
                    peripheral_id='sc-sensor', current_value=value, target_value=sc_sensor.targetValue,
                ))
                await self.log_event('info', f'SC Sensor: {value:.1f} bar')

        # Update WC sensor if valve is open
        valve_wc = self.state_manager.peripherals.get('valve-wc')
        if valve_wc and valve_wc.currentValue:
            wc_sensor = self.state_manager.peripherals.get('wc-sensor')
            if wc_sensor:
                value = pump_power * 4  # 400 bar at 100% power
                bus.dispatch(SetPeripheralValueCommand(
                    peripheral_id='wc-sensor', current_value=value, target_value=wc_sensor.targetValue,
                ))
                await self.log_event('info', f'WC Sensor: {value:.1f} bar')
        
        # Broadcast peripheral updates
        for peripheral in self.state_manager.peripherals.values():
            await self.state_manager.broadcast_event({
                'type': 'peripheral_update',
                'peripheral': peripheral.model_dump()  # Use model_dump instead of deprecated dict()
            })
    
    async def validate_goal(self, goal: Goal):
        """Validate goal completion"""
        all_valid = True
        for rule in goal.validationCriteria:
            if rule.peripheral in self.state_manager.peripherals:
                peripheral = self.state_manager.peripherals[rule.peripheral]
                # Simple evaluation (in production, use safe evaluation)
                context = {
                    'value': peripheral.currentValue,
                    'leakRate': 0  # Placeholder for leak rate calculation
                }
                try:
                    result = safe_eval_condition(rule.condition, context)
                    if not result:
                        await self.log_event('error', rule.errorMessage)
                        all_valid = False
                except Exception as ex:
                    await self.log_event('error', f'Failed to evaluate: {rule.condition} ({ex})')
                    all_valid = False
        return all_valid
    
    async def log_event(self, level: str, message: str):
        """Log event and broadcast to clients"""
        timestamp = datetime.now(timezone.utc).isoformat()
        event = {
            'type': 'event',
            'timestamp': timestamp,
            'level': level,
            'message': message
        }
        
        await self.state_manager.broadcast_event(event)

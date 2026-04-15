"""
Hardware plugin CLI - manage and configure hardware plugins.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from oqlos.hardware.plugins import (
    HardwarePlugin,
    PluginConfig,
    PluginHealth,
    PluginRegistry,
    PiadcPlugin,
    MotorPlugin,
    ModbusPlugin,
    LungPlugin,
)


# Register built-in plugins
PluginRegistry.register(PiadcPlugin)
PluginRegistry.register(MotorPlugin)
PluginRegistry.register(ModbusPlugin)
PluginRegistry.register(LungPlugin)


def _load_config_file(path: str) -> dict[str, PluginConfig]:
    """Load plugin configurations from a YAML or JSON file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path) as f:
        if config_path.suffix in [".yaml", ".yml"]:
            data = yaml.safe_load(f)
        else:
            data = json.load(f)

    configs = {}
    for plugin_id, config_data in data.get("plugins", {}).items():
        configs[plugin_id] = PluginConfig(
            plugin_id=plugin_id,
            enabled=config_data.get("enabled", True),
            connection_type=config_data.get("connection_type", "http"),
            connection_params=config_data.get("connection_params", {}),
            timeout=config_data.get("timeout", 5.0),
            retry_count=config_data.get("retry_count", 3),
            metadata=config_data.get("metadata", {}),
        )
    return configs


def _save_config_file(path: str, configs: dict[str, PluginConfig]) -> None:
    """Save plugin configurations to a YAML file."""
    data = {
        "plugins": {
            plugin_id: {
                "enabled": config.enabled,
                "connection_type": config.connection_type,
                "connection_params": config.connection_params,
                "timeout": config.timeout,
                "retry_count": config.retry_count,
                "metadata": config.metadata,
            }
            for plugin_id, config in configs.items()
        }
    }

    config_path = Path(path)
    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


async def cmd_list(args: argparse.Namespace) -> None:
    """List all registered plugins."""
    plugins = PluginRegistry.list_plugins()
    print("Registered plugins:")
    for plugin in plugins:
        print(f"  - {plugin['plugin_id']}: {plugin['name']} (v{plugin['version']})")
        print(f"    Description: {plugin['description']}")
        print(f"    Protocols: {', '.join(plugin['supported_protocols'])}")
        print(f"    Required packages: {', '.join(plugin['required_packages']) or 'none'}")
        print()


async def cmd_status(args: argparse.Namespace) -> None:
    """Show status of all plugins."""
    status = PluginRegistry.get_status()
    print(f"Registered plugins: {status['registered_plugins']}")
    print(f"Active instances: {status['active_instances']}")
    print("\nPlugin instances:")
    for plugin in status["plugins"]:
        print(f"  - {plugin['plugin_id']}: {plugin['status']} (connected: {plugin['connected']})")


async def cmd_capabilities(args: argparse.Namespace) -> None:
    """Show capabilities of a specific plugin."""
    plugin_class = PluginRegistry.get_plugin_class(args.plugin_id)
    if not plugin_class:
        print(f"Plugin '{args.plugin_id}' not found", file=sys.stderr)
        sys.exit(1)

    capabilities = plugin_class.get_capabilities()
    print(yaml.dump(capabilities, default_flow_style=False, sort_keys=False))


async def cmd_validate(args: argparse.Namespace) -> None:
    """Validate plugin configurations."""
    if args.config:
        try:
            configs = _load_config_file(args.config)
        except Exception as exc:
            print(f"Failed to load config file: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        # Validate single plugin
        config = PluginConfig(
            plugin_id=args.plugin_id,
            connection_type=args.connection_type or "http",
            connection_params=json.loads(args.params) if args.params else {},
        )
        configs = {args.plugin_id: config}

    errors = PluginRegistry.validate_all_configurations(configs)
    if errors:
        print("Configuration errors:")
        for plugin_id, plugin_errors in errors.items():
            print(f"  {plugin_id}:")
            for error in plugin_errors:
                print(f"    - {error}")
        sys.exit(1)
    else:
        print("All configurations are valid")


async def cmd_connect(args: argparse.Namespace) -> None:
    """Connect to a hardware plugin."""
    config = PluginConfig(
        plugin_id=args.plugin_id,
        connection_type=args.connection_type or "http",
        connection_params=json.loads(args.params) if args.params else {},
    )

    success = await PluginRegistry.connect_plugin(args.plugin_id, config)
    if success:
        print(f"Connected to plugin '{args.plugin_id}'")
    else:
        print(f"Failed to connect to plugin '{args.plugin_id}'", file=sys.stderr)
        sys.exit(1)


async def cmd_disconnect(args: argparse.Namespace) -> None:
    """Disconnect from a hardware plugin."""
    success = await PluginRegistry.disconnect_plugin(args.plugin_id)
    if success:
        print(f"Disconnected from plugin '{args.plugin_id}'")
    else:
        print(f"Failed to disconnect from plugin '{args.plugin_id}'", file=sys.stderr)
        sys.exit(1)


async def cmd_health(args: argparse.Namespace) -> None:
    """Check health of plugins."""
    if args.plugin_id:
        health = await PluginRegistry.health_check(args.plugin_id)
        if health:
            print(yaml.dump({
                "status": health.status.value,
                "message": health.message,
                "compatible": health.compatible,
                "version": health.version,
                "details": health.details,
            }, default_flow_style=False, sort_keys=False))
        else:
            print(f"No active instance for plugin '{args.plugin_id}'", file=sys.stderr)
            sys.exit(1)
    else:
        health_results = await PluginRegistry.health_check_all()
        print(yaml.dump(health_results, default_flow_style=False, sort_keys=False))


async def cmd_execute(args: argparse.Namespace) -> None:
    """Execute a command on a hardware plugin."""
    instance = PluginRegistry.get_instance(args.plugin_id)
    if not instance:
        print(f"No active instance for plugin '{args.plugin_id}'", file=sys.stderr)
        sys.exit(1)

    params = json.loads(args.params) if args.params else {}
    result = await instance.execute_command(args.command, params)
    print(yaml.dump(result, default_flow_style=False, sort_keys=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="oqlctl plugin",
        description="Hardware plugin management CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Plugin commands")

    # List command
    subparsers.add_parser("list", help="List all registered plugins")

    # Status command
    subparsers.add_parser("status", help="Show status of all plugins")

    # Capabilities command
    caps_parser = subparsers.add_parser("capabilities", help="Show plugin capabilities")
    caps_parser.add_argument("plugin_id", help="Plugin ID")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate plugin configurations")
    validate_parser.add_argument("--config", help="Path to config file (YAML/JSON)")
    validate_parser.add_argument("--plugin-id", help="Single plugin ID to validate")
    validate_parser.add_argument("--connection-type", help="Connection type")
    validate_parser.add_argument("--params", help="Connection params as JSON string")

    # Connect command
    connect_parser = subparsers.add_parser("connect", help="Connect to a plugin")
    connect_parser.add_argument("plugin_id", help="Plugin ID")
    connect_parser.add_argument("--connection-type", help="Connection type")
    connect_parser.add_argument("--params", help="Connection params as JSON string")

    # Disconnect command
    disconnect_parser = subparsers.add_parser("disconnect", help="Disconnect from a plugin")
    disconnect_parser.add_argument("plugin_id", help="Plugin ID")

    # Health command
    health_parser = subparsers.add_parser("health", help="Check plugin health")
    health_parser.add_argument("--plugin-id", help="Specific plugin ID (default: all)")

    # Execute command
    exec_parser = subparsers.add_parser("execute", help="Execute a command on a plugin")
    exec_parser.add_argument("plugin_id", help="Plugin ID")
    exec_parser.add_argument("command", help="Command to execute")
    exec_parser.add_argument("--params", help="Command params as JSON string")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    async def run_command():
        if args.command == "list":
            await cmd_list(args)
        elif args.command == "status":
            await cmd_status(args)
        elif args.command == "capabilities":
            await cmd_capabilities(args)
        elif args.command == "validate":
            await cmd_validate(args)
        elif args.command == "connect":
            await cmd_connect(args)
        elif args.command == "disconnect":
            await cmd_disconnect(args)
        elif args.command == "health":
            await cmd_health(args)
        elif args.command == "execute":
            await cmd_execute(args)

    asyncio.run(run_command())


if __name__ == "__main__":
    main()

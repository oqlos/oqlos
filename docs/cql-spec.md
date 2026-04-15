<!-- code2docs:start --># dsl

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.9-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-193-green)
> **193** functions | **40** classes | **24** files | CC̄ = 3.3

> Auto-generated project documentation from source code analysis.

**Author:** Tom Softreck <tom@sapletta.com>  
**License:** Not specified  
**Repository:** [https://github.com/zlecenia/c2004](https://github.com/zlecenia/c2004)

## Installation

### From PyPI

```bash
pip install dsl
```

### From Source

```bash
git clone https://github.com/zlecenia/c2004
cd dsl
pip install -e .
```


## Quick Start

### CLI Usage

```bash
# Generate full documentation for your project
dsl ./my-project

# Only regenerate README
dsl ./my-project --readme-only

# Preview what would be generated (no file writes)
dsl ./my-project --dry-run

# Check documentation health
dsl check ./my-project

# Sync — regenerate only changed modules
dsl sync ./my-project
```

### Python API

```python
from dsl import generate_readme, generate_docs, Code2DocsConfig

# Quick: generate README
generate_readme("./my-project")

# Full: generate all documentation
config = Code2DocsConfig(project_name="mylib", verbose=True)
docs = generate_docs("./my-project", config=config)
```

## Generated Output

When you run `dsl`, the following files are produced:

```
<project>/
├── README.md                 # Main project README (auto-generated sections)
├── docs/
│   ├── api.md               # Consolidated API reference
│   ├── modules.md           # Module documentation with metrics
│   ├── architecture.md      # Architecture overview with diagrams
│   ├── dependency-graph.md  # Module dependency graphs
│   ├── coverage.md          # Docstring coverage report
│   ├── getting-started.md   # Getting started guide
│   ├── configuration.md    # Configuration reference
│   └── api-changelog.md    # API change tracking
├── examples/
│   ├── quickstart.py       # Basic usage examples
│   └── advanced_usage.py   # Advanced usage examples
├── CONTRIBUTING.md         # Contribution guidelines
└── mkdocs.yml             # MkDocs site configuration
```

## Configuration

Create `dsl.yaml` in your project root (or run `dsl init`):

```yaml
project:
  name: my-project
  source: ./
  output: ./docs/

readme:
  sections:
    - overview
    - install
    - quickstart
    - api
    - structure
  badges:
    - version
    - python
    - coverage
  sync_markers: true

docs:
  api_reference: true
  module_docs: true
  architecture: true
  changelog: true

examples:
  auto_generate: true
  from_entry_points: true

sync:
  strategy: markers    # markers | full | git-diff
  watch: false
  ignore:
    - "tests/"
    - "__pycache__"
```

## Sync Markers

dsl can update only specific sections of an existing README using HTML comment markers:

```markdown
<!-- dsl:start -->
# Project Title
... auto-generated content ...
<!-- dsl:end -->
```

Content outside the markers is preserved when regenerating. Enable this with `sync_markers: true` in your configuration.

## Architecture

```
dsl/
├── project        ├── config        ├── main├── nfo_config    ├── base├── interpreter/    ├── __main__├── main        ├── cli    ├── cql/    ├── firmware_adapter        ├── parser        ├── models    ├── example-map    ├── types├── core/    ├── event_store├── models/        ├── interpreter    ├── iql├── api/    ├── event-server    ├── dsl-shell├── client/```

## API Overview

### Classes

- **`DslSchema`** — —
- **`DslEditorApp`** — —
- **`FirmwareAdapter`** — HTTP bridge between CQL interpreter and firmware simulator.
- **`CqlMetadata`** — —
- **`CqlInterval`** — —
- **`CqlCondition`** — Sensor condition: AI01 ∈ [min, max] unit | ACTION 'msg'
- **`CqlAction`** — An action within a step: → Target.method args, TASK, SET, WAIT, or PUMP.
- **`CqlStep`** — A numbered step within a goal: 1. Step name:
- **`CqlGoal`** — A test goal within a scenario.
- **`CqlScenario`** — A named scenario block: @Namespace.Name
- **`CqlDocument`** — Root AST node for a .cql file.
- **`ApiCommand`** — —
- **`ActionCommand`** — —
- **`ComponentDefinition`** — —
- **`ComponentCommand`** — —
- **`UIState`** — —
- **`StateCommand`** — —
- **`ProcessStep`** — —
- **`ProcessDefinition`** — —
- **`ProcessInstance`** — —
- **`ProcessCommand`** — —
- **`SessionRecording`** — —
- **`SessionCommand`** — —
- **`ReplayCommand`** — —
- **`DslExecutionContext`** — —
- **`DslExecutionResult`** — —
- **`DslEventStore`** — Append-only event store with optional JSON file persistence.
- **`CqlInterpreter`** — CQL interpreter with three modes:
- **`IqlLine`** — —
- **`IqlScript`** — —
- **`IqlInterpreter`** — IQL interpreter — runs .iql scripts.
- **`EventServer`** — —
- **`DslExecutor`** — Execute DSL commands
- **`ShellCommandRegistry`** — Registry for interactive shell commands.
- **`DslFunction`** — —
- **`DslObject`** — —
- **`DslParam`** — —
- **`DslUnit`** — —
- **`Variable`** — —
- **`DslClient`** — Client for DSL Service API

### Functions

- `main()` — —
- `parse_cql(source, filename)` — Parse CQL source into AST.
- `validate_cql(doc)` — Validate a parsed CQL document. Returns list of issues.
- `dsl()` — —
- `exec()` — —
- `run()` — —
- `navigate()` — —
- `startRecording()` — —
- `stopRecording()` — —
- `replay()` — —
- `session()` — —
- `connect()` — —
- `parse_iql(source, filename)` — Parse IQL source into command list.
- `main()` — —
- `health()` — —
- `list_functions()` — —
- `list_objects()` — —
- `list_params()` — —
- `list_units()` — —
- `list_variables()` — —
- `get_schema()` — Get complete DSL schema - returns empty (tables removed in c40)
- `create_tables()` — No-op - tables removed
- `main()` — —
- `run_shell()` — Run interactive DSL shell
- `run_script(filename)` — Execute DSL script file
- `run_command(command)` — Execute single command
- `main()` — —
- `create_client(base_url)` — —


## Project Structure

📦 `api` (8 functions)
📄 `cli.dsl-shell` (45 functions, 2 classes)
📦 `client` (24 functions, 6 classes)
📦 `core` (9 functions)
📄 `core.event_store` (10 functions, 1 classes)
📄 `core.types` (15 classes)
📄 `frontend.src.main` (33 functions, 2 classes)
📄 `frontend.vite.config`
📦 `interpreter`
📄 `interpreter.__main__`
📄 `interpreter.base`
📦 `interpreter.cql`
📄 `interpreter.cql.cli` (1 functions)
📄 `interpreter.cql.interpreter` (13 functions, 1 classes)
📄 `interpreter.cql.models` (8 classes)
📄 `interpreter.cql.parser` (9 functions)
📄 `interpreter.firmware_adapter` (16 functions, 1 classes)
📄 `interpreter.iql` (30 functions, 3 classes)
📄 `main`
📄 `maps.example-map`
📦 `models`
📄 `nfo_config`
📄 `project`
📄 `server.event-server` (6 functions, 1 classes)

## Requirements

- fastapi >=0.104.0- uvicorn >=0.24.0- sqlalchemy >=2.0.0- pydantic >=2.5.0- httpx >=0.25.0- nfo >=0.2.3

## Contributing

**Contributors:**
- Tom Softreck <tom@sapletta.com>
- Tom Sapletta <tom@sapletta.com>
- Tom Sapletta <tom-sapletta-com@users.noreply.github.com>
- zlecenia <zlecenia@c2004.pl>

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/zlecenia/c2004
cd dsl

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Documentation

- 📖 [Full Documentation](https://github.com/zlecenia/c2004/tree/main/docs) — API reference, module docs, architecture
- 🚀 [Getting Started](https://github.com/zlecenia/c2004/blob/main/docs/getting-started.md) — Quick start guide
- 📚 [API Reference](https://github.com/zlecenia/c2004/blob/main/docs/api.md) — Complete API documentation
- 🔧 [Configuration](https://github.com/zlecenia/c2004/blob/main/docs/configuration.md) — Configuration options
- 💡 [Examples](./examples) — Usage examples and code samples

### Generated Files

| Output | Description | Link |
|--------|-------------|------|
| `README.md` | Project overview (this file) | — |
| `docs/api.md` | Consolidated API reference | [View](./docs/api.md) |
| `docs/modules.md` | Module reference with metrics | [View](./docs/modules.md) |
| `docs/architecture.md` | Architecture with diagrams | [View](./docs/architecture.md) |
| `docs/dependency-graph.md` | Dependency graphs | [View](./docs/dependency-graph.md) |
| `docs/coverage.md` | Docstring coverage report | [View](./docs/coverage.md) |
| `docs/getting-started.md` | Getting started guide | [View](./docs/getting-started.md) |
| `docs/configuration.md` | Configuration reference | [View](./docs/configuration.md) |
| `docs/api-changelog.md` | API change tracking | [View](./docs/api-changelog.md) |
| `CONTRIBUTING.md` | Contribution guidelines | [View](./CONTRIBUTING.md) |
| `examples/` | Usage examples | [Browse](./examples) |
| `mkdocs.yml` | MkDocs configuration | — |

<!-- code2docs:end -->
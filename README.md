# pyssp_interface

Graphical interface for building and interacting with SSP and FMUs.

The current app can:

- open and inspect SSP archives
- inspect FMU metadata and variables
- browse nested SSD structures in a recursive tree
- render subsystem-scoped block diagrams
- author components, system connectors, and connections through path-based service operations

## Getting Started

The main onboarding flow is in [docs/getting_started.md](docs/getting_started.md).

Quick setup:

```bash
python3 -m venv venv
. venv/bin/activate
python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e '.[dev]'
```

Run the application:

```bash
. venv/bin/activate
pyssp-interface
```

## Documentation

- [Docs index](docs/index.md)
- [Getting started](docs/getting_started.md)
- [Architecture](docs/dev/architecture.md)
- [Implementation plan](docs/dev/implementation_plan.md)

# pyssp_interface

Graphical interface for building and interacting with SSP and FMUs

## Development

Create a repo-local virtual environment and install the application in editable mode:

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
- [Implementation plan](docs/dev/implementation_plan.md)

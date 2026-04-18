# Getting Started

This page is for developers working on `pyssp_interface` locally.

## What You Can Do

- install the app in a repo-local environment
- run the desktop UI
- run the current service-level test suite

## Setup

```bash
python3 -m venv venv
. venv/bin/activate
python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e '.[dev]'
```

## Run

```bash
. venv/bin/activate
pyssp-interface
```

## Verify

```bash
. venv/bin/activate
python -m pytest tests/unit/test_project_service.py
python -m compileall src tests
```

## Current Scope

The current application can:

- open and inspect SSP archives
- inspect FMUs inside project resources
- render nested SSD structure in the left-hand tree
- render a subsystem-scoped block diagram view
- author connectors, components, and connections through path-based service operations

The primary architectural direction is now:

- nested authoring as a first-class requirement
- block diagram editing as the future primary editing surface
- continued modularization away from `MainWindow`

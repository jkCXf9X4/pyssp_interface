# Code Guidelines

This page is for maintainers working on `pyssp_interface`.

## Goals

- keep modules small enough to scan quickly
- keep each module focused on one responsibility
- make it obvious where new code belongs
- prefer structures that are easy for both humans and AI agents to navigate

## Module Size Rules

- Prefer modules under 300 lines.
- Treat 400 lines as a refactor trigger.
- Treat 600 lines as a strong smell unless the file is intentionally data-heavy.
- UI orchestration modules should shrink over time, not grow.

If a file grows because it mixes concerns, split by responsibility before adding more behavior.

## Separation Rules

- `services/`
  - own SSP and FMU mutation logic
  - no widget-specific behavior
- `state/`
  - own typed UI-facing data and project lookup/index helpers
  - no Qt widget behavior
- `widgets/`
  - own reusable Qt widget construction and rendering helpers
  - no project mutation rules
- `presentation/`
  - own formatting and display transformations
  - no direct SSP mutation
- `main_window.py`
  - should compose views and route actions
  - should not accumulate project traversal utilities, table helper code, or domain rules

## Refactor Triggers

Split code when one function or module starts doing more than one of these jobs:

- traversing the project tree or structure model
- formatting display text
- constructing or populating widgets
- handling domain mutations
- storing interaction state

Examples in the current codebase:

- project traversal belongs in `state/project_index.py`
- diagram interaction state belongs in `diagram_controller.py`
- generic table setup belongs in `widgets/table_helpers.py`

## Data Structure Rules

- Prefer typed dataclasses or `TypedDict` for reused payload shapes.
- If a dict shape is used in more than one place, give it a named type.
- Keep payloads close to the layer that owns them.

## Duplication Rules

- If two call sites repeat the same lookup sequence, extract it.
- If two widgets use the same table setup logic, share it.
- If two UI flows call the same domain mutation, route both through one helper method.

## Review Checklist

Before finishing a change, check:

- Is the new code in the right layer?
- Did this make a large module larger when it should have been split?
- Did I introduce a repeated dict shape without naming it?
- Did I duplicate table, lookup, or mutation logic that already exists?

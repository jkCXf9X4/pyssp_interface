# Architecture

This page describes the current implementation shape of `pyssp_interface` and the next architectural direction.

## Current Structure

The application is currently split into a few concrete layers:

- `services/project_service.py`
  - wraps `pyssp_standard`
  - owns project open/create/import/edit operations
  - resolves nested system paths for write operations
- `state/project_state.py`
  - defines UI-facing summary objects
  - represents recursive SSD structure through `StructureNode`
- `widgets/project_tree.py`
  - renders the nested project and SSD tree
  - keeps tree payload handling out of `MainWindow`
- `presentation/formatters.py`
  - owns text-formatting for inspector/detail panels
- `diagram_controller.py`
  - owns diagram selection state, connection-creation flow, and layout coordination
  - keeps diagram interaction rules out of `MainWindow`
- `diagram_view.py`
  - renders one system scope at a time
  - shows nested systems as collapsed subsystem blocks in parent scopes
- `main_window.py`
  - still coordinates the application
  - now delegates tree construction, text formatting, and diagram interaction state to focused modules

## Nested Authoring Model

Nested authoring is a near-term requirement and is now part of the service contract.

The service layer supports:

- `system_path` for targeting the system being edited
- full owner paths for connection endpoints
- validation against the local system scope instead of a flattened project-wide namespace

This is the key shift that makes subsystem editing viable and gives the diagram a stable command model to build on.

## Diagram Direction

The block diagram is no longer treated as a secondary visualization only.

Current behavior:

- a selected system renders as its own diagram scope
- child systems render as collapsed subsystem blocks in the parent scope
- tree selection and diagram selection stay synchronized
- connector selection and connection creation work directly from the diagram
- block movement updates in-memory layout state per system scope

Planned direction:

- per-system layout state instead of hardcoded procedural placement
- connection deletion and broader edit flows from the diagram
- diagram-first editing with forms/tables as secondary precision tools

## Current Constraints

- `MainWindow` still owns broad selection/details orchestration even though diagram-specific state moved out
- diagram layout is still in-memory only and not persisted
- service/controller tests are stronger than UI tests
- parameter binding editing is still shallow

## Next Refactor Targets

- introduce persistent layout state per system scope
- expand tests around nested authoring and subsystem editing flows
- continue splitting selection/details orchestration out of `MainWindow`
- keep new functionality routed through path-based service commands first, then expose it in the diagram

# Implementation Plan

This document describes a pragmatic implementation plan for `pyssp_interface`, a Python desktop application for building, inspecting, and editing SSP archives and FMUs on top of `pyssp_standard`.

## Project Goal

Build a desktop application that makes common SSP and FMU workflows accessible without requiring users to manually edit XML or zip archives.

The application should:

- create and edit SSP projects
- inspect FMUs and expose their variables, units, and metadata
- build SSP system structures around imported FMUs
- provide a block diagram editing view for arranging components and editing connections visually
- manage resources such as `.fmu`, `.ssv`, `.ssm`, `.ssb`, and related files
- edit table resources such as `.ssv`, `.ssm`
- validate and save archives through `pyssp_standard`
- leave room for future simulation-oriented workflows without coupling the first version to a simulator backend

## Current Starting Point

The repository currently contains:

- a minimal top-level project scaffold
- `3rd_party/pyssp_standard`, which already supports reading and writing SSP-related files and reading FMU metadata
- `3rd_party/pyfmu_csv`, which can generate a simple FMI 2.0 Co-Simulation FMU from CSV data and may serve as an early FMU authoring workflow

`pyssp_standard` already provides the most important domain model building blocks:

- `SSP` for archive/resource management
- `SSD`, `System`, `Component`, `Connector`, and `Connection` for system structure editing
- `SSV`, `SSM`, `SSB`, and `SRMD` for related SSP content
- `FMU` and `ModelDescription` for FMU inspection

This means the GUI should be implemented as an application layer on top of the library, not as a parallel SSP model implementation.

## Current Implementation Status

The repository is now past the original bootstrap stage and has a working vertical slice for SSP inspection and basic authoring.

### Completed

- packaged `src/` application with a repo-local `venv` workflow
- `SSPProjectService` for open/create/import/edit operations
- recursive `StructureNode` model for nested SSD structure
- nested tree view tied to actual SSD ownership paths
- subsystem-scoped diagram rendering
- path-based nested authoring APIs for connectors, components, and connections
- diagram-side endpoint selection and connection creation
- diagram interaction/controller extraction out of `MainWindow`
- focused unit coverage for project service, diagram layout, and diagram controller behavior

### In Progress

- diagram-first editing workflows beyond connection authoring
- persistent layout state per system scope
- broader nested-authoring test coverage beyond the current service/controller focus
- tabular editors for variable tables, composition tables, SSV, and SSM add/update/delete workflows

### Not Started

- parameter binding editing beyond the existing structural placeholders
- resource management actions such as rename, duplicate, and remove
- extended SSP asset editors for `.ssb` and SRMD content
- FMU authoring helpers built on `pyfmu_csv`

## Tracking Snapshot

Use this section as the canonical high-level tracker.

### Delivery Phases Status

- Phase 0: complete
- Phase 1: complete
- Phase 2: mostly complete
  Remaining gaps: explicit save/save-as workflow, dirty-state tracking, and stronger project lifecycle ergonomics.
- Phase 3: in progress
  Remaining gaps: visual deletion/movement flows beyond current basics, layout persistence, and deeper diagram-first editing.
- Phase 4: not started
- Phase 5: not started

### Workstream Status

- Workstream 1: in progress
  Implemented: create/open existing project and archive-backed edits.
  Remaining: save/save-as UX, dirty-state tracking, and temp/project state management.
- Workstream 2: mostly complete
  Implemented: FMU import, FMU inspection, variable display, and component generation from FMU metadata.
  Remaining: richer FMU presentation grouping and polish, not foundational capability.
- Workstream 3: in progress
  Implemented: nested system editing for components, connectors, and connections.
  Remaining: remove/edit component flows, tabular editors for composition and related variable data, and basic parameter binding workflows.
- Workstream 4: in progress
  Implemented: scoped diagram rendering, synchronized selection, connector picking, connection creation, and in-memory block placement.
  Remaining: persistent layout state, broader visual edit/delete flows, and more complete diagram-first authoring.
- Workstream 5: in progress
  Implemented: validation messages surfaced from SSD checks in the UI.
  Remaining: stronger diagnostics, earlier invalid-connection feedback, and better object-linked error reporting.
- Workstream 6: in progress
  Remaining: tabular editors for SSV and SSM item CRUD, then broader `.ssb` and SRMD support.
- Workstream 7: not started

## Proposed Product Scope

The first useful product should focus on authoring and inspection, not on full simulation orchestration.

### In Scope for MVP

- create a new SSP project
- open an existing `.ssp` archive
- browse archive resources and system structure
- import one or more FMUs into the project resources
- inspect FMU inputs, outputs, parameters, and units
- add components to the top-level system from imported FMUs
- create, edit, and delete connectors and connections
- manage parameter bindings at a basic level
- provide an initial block diagram editing view for component placement, selection, and connection editing
- save changes back to an SSP archive
- run structural validation and present errors in the UI

### Out of Scope for MVP

- full graphical diagram auto-layout
- full SSV/SSM/SSB editors with advanced schema-specific UX
- simulation execution, co-simulation master algorithms, or result plotting
- rich undo/redo across all editor operations
- multi-user collaboration

## Recommended Technical Direction

Use `PySide6` for the GUI.

Reasoning:

- mature Python desktop toolkit with strong model/view support
- good fit for a multi-pane engineering desktop application
- supports tree views, tables, dialogs, dockable layouts, and custom graphics scenes
- easier to structure for long-lived desktop workflows than a web UI inside this repository

Avoid making the whole product depend on a sophisticated node editor up front. The first version should use conventional desktop patterns plus a focused diagram editor:

- project tree
- inspector/details pane
- tabbed editors
- tables/forms for connectors, connections, and parameters
- a block diagram canvas for visual editing of components and connections

The diagram editor should be added after the object model and service layer are stable enough to support it cleanly, but it is part of the intended product rather than an optional extra.

## Proposed Architecture

Keep the codebase split into clear layers.

### 1. Domain Integration Layer

Purpose: isolate direct usage of `pyssp_standard`.

Responsibilities:

- open/create/save SSP archives
- import FMUs and extract metadata
- translate FMU metadata into suggested SSP components/connectors
- wrap common archive edit operations into application-level services
- centralize validation and error normalization

This layer should be thin but real. The goal is not to re-implement `pyssp_standard`, but to keep UI code from manipulating archive internals everywhere.

### 2. Application State Layer

Purpose: represent the current project/session in UI-friendly form.

Responsibilities:

- track opened project, selected item, dirty state, and validation state
- expose tree and table models for Qt views
- map user actions to domain operations
- handle save/load/import workflows

Prefer explicit state objects over ad hoc mutation spread across widgets.

### 3. UI Layer

Purpose: present and edit SSP/FMUs through desktop workflows.

Initial views:

- main window shell
- project/resource tree
- FMU inspector
- system structure editor
- block diagram editor
- connection editor
- validation/errors panel

### 4. Packaging Layer

Purpose: ship the application as a usable desktop tool.

Responsibilities:

- Python packaging
- reproducible local development setup
- desktop build/distribution process

## Suggested Repository Layout

One reasonable initial structure is:

```text
docs/
  index.md
  dev/
    implementation_plan.md
src/
  pyssp_interface/
    app.py
    diagram_controller.py
    main_window.py
    state/
    services/
    widgets/
tests/
  unit/
  integration/
```

Notes:

- `services/` owns interactions with `pyssp_standard` and `pyfmu_csv`
- `widgets/` holds focused Qt widgets such as the project tree
- `state/` holds application/session state objects
- controller-style modules can sit at the package root while the UI is still small

## Functional Workstreams

Implement the project through a small number of stable workstreams.

### Workstream 1: Project Lifecycle

- done: create a new empty SSP project
- done: open an existing SSP
- remaining: save and save as
- remaining: detect dirty state
- remaining: manage unpacked temp/project state safely

### Workstream 2: FMU Import and Inspection

- done: import FMUs into `resources/`
- done: inspect `modelDescription.xml` via `pyssp_standard.FMU`
- done: present FMU variables in the UI
- done: generate suggested SSP connectors/components from FMU metadata
- remaining: improve FMU variable grouping/presentation polish

### Workstream 3: System Structure Editing

- done: edit `SystemStructure.ssd` at any system depth
- done: add components
- remaining: remove components
- done: create connectors
- remaining: edit/delete connectors
- done: create/delete connections
- remaining: tabular editors for add/edit/delete composition and variable rows tied to components, connectors, and connections
- remaining: support simple parameter bindings

### Workstream 4: Block Diagram Editing

- done: provide a canvas-based view of the current SSP system structure
- done: render components, system connectors, and directed connections
- done: support selection and synchronized inspection with the details pane
- in progress: support create/move/delete actions for components and connections
- done: keep the visual editor backed by the same domain operations as the form/table editors
- remaining: store layout metadata in annotations or another persistent representation

### Workstream 5: Validation and Diagnostics

- done: surface schema/compliance errors
- remaining: detect invalid connection patterns before save where possible
- remaining: show user-facing messages with references to the affected object

### Workstream 6: Extended Asset Editing

After the MVP unless pulled forward by table-editing work:

- in progress: tabular editors for SSV and SSM viewing plus add/modify/remove item workflows
- SSB browser/editor
- SRMD workflow support

### Workstream 7: FMU Authoring Helpers

After the MVP:

- integrate `pyfmu_csv` as a guided wizard for creating simple CSV-backed FMUs
- create import templates from generated FMUs
- expose packaged runtime requirements clearly in the UI

## Delivery Phases

### Phase 0: Bootstrap

Goal: establish a usable application skeleton.

Deliverables:

- `src/` layout
- Python packaging metadata
- `PySide6` dependency setup
- application entry point
- main window with placeholder panes
- test harness for non-UI services

Exit criteria:

- app launches locally
- project contains a repeatable development workflow

Status: complete

### Phase 1: Read-Only Explorer

Goal: make existing SSPs and FMUs inspectable.

Deliverables:

- open SSP archive
- display resources and system structure tree
- inspect FMU metadata
- validation panel for load/open errors

Exit criteria:

- user can open an SSP and understand its contents without leaving the app

Status: complete

### Phase 2: Basic SSP Authoring

Goal: support the core editing loop.

Deliverables:

- create new project
- import FMU into resources
- add component from FMU
- edit system connectors and connections
- save archive

Exit criteria:

- user can create a small SSP around one or more FMUs and save it successfully

Status: mostly complete
Remaining:

- explicit save/save-as workflow in the UI
- clearer dirty-state handling

### Phase 3: Visual Editing

Goal: add a usable block diagram editor on top of the stable authoring model.

Deliverables:

- block diagram canvas for components and system connectors
- visual creation and deletion of connections
- selection sync between diagram, tree, and inspector
- basic component placement and movement
- persistence for diagram layout data

Exit criteria:

- user can build and adjust a small system visually without dropping back to raw structural forms for every edit

Status: in progress
Implemented so far:

- block diagram canvas for systems and subsystem scopes
- selection sync between diagram, tree, and inspector
- visual connection creation
- basic block movement with in-memory layout state

Remaining:

- persistence for diagram layout data
- broader visual delete/edit flows
- further reduction of `MainWindow` orchestration as the UI grows

### Phase 4: Parameter and Resource Workflows

Goal: round out the minimum engineering workflow.

Deliverables:

- basic parameter binding editor
- tabular editors for variable tables, composition tables, SSV, and SSM add/update/delete actions
- resource management actions
- duplicate/rename/remove actions where safe
- stronger validation and better diagnostics

Exit criteria:

- user can manage an SSP project without manual archive surgery

Status: not started

### Phase 5: Guided Generation and Polishing

Goal: improve usability and add leverage.

Deliverables:

- wizard-driven create/import flows
- optional `pyfmu_csv` integration
- better editing affordances
- packaging for desktop distribution

Exit criteria:

- app is practical for regular use by non-library-developer users

Status: not started

## First Implementation Slice

The best first slice is:

1. create application skeleton with `PySide6`
2. implement a service that opens an SSP and exposes:
   - resource list
   - root SSD
   - FMU summaries
3. render that data in:
   - a project tree
   - an FMU variable inspector
   - a text-based validation/error panel

This slice is valuable because it exercises the hardest integration boundary early:

- archive handling
- FMU inspection
- mapping domain objects into UI models

without forcing immediate decisions about full editing UX.

## Block Diagram View Notes

The block diagram editor should be treated as a first-class editing surface, not just a visualization.

Recommended implementation approach:

- start with `QGraphicsScene` and `QGraphicsView`
- represent SSP components as movable block items
- represent nested `System` nodes as collapsed subsystem blocks in parent scopes
- represent system connectors and FMU connectors as ports on those blocks
- represent `Connection` objects as directed edges
- keep editing commands routed through the same service/state layer used by non-visual editors

Recommended constraints for the first version:

- support manual placement before introducing auto-layout
- prefer stable, inspectable data flow over polished graphics
- keep a table/form editor available alongside the canvas for precise editing and debugging

## Testing Strategy

Keep UI tests light and keep most behavior testable outside widgets.

### Unit Tests

- service-level SSP open/save/import logic
- FMU metadata extraction and mapping
- validation normalization
- tree/table model behavior where practical

### Integration Tests

- open sample SSPs from `pyssp_standard/pytest/doc`
- import FMUs from existing test fixtures
- save and reopen modified SSPs

### Manual Acceptance Checks

- create a project from scratch
- import a real FMU
- create components and connections
- save, reopen, and verify structure

## Risks and Design Constraints

### Risk: Over-coupling UI to library internals

Mitigation:

- keep `pyssp_standard` access in services/state adapters
- avoid direct archive mutation from widgets

### Risk: Root-only editing contracts

Mitigation:

- make all write operations accept `system_path`
- use full owner paths for connection endpoints
- treat nested authoring as a baseline capability, not a later extension

### Risk: Unclear write semantics for some SSP subformats

Mitigation:

- start with the flows already well-supported by `pyssp_standard`
- explicitly defer complex editors until proven needed

### Risk: Premature graphical canvas work

Mitigation:

- ship list/form/table editors first
- add a diagram view only after core editing actions are stable

### Risk: Platform-specific packaging complexity

Mitigation:

- validate the app in development mode first
- treat desktop packaging as a later workstream, not a day-one blocker

## Immediate Next Steps

Recommended next implementation tasks:

1. introduce persistent layout state per system scope
2. expand nested-authoring tests beyond the current service/controller coverage
3. add visual delete/edit flows for diagram-authored connections and components
4. add tabular editors for variable tables, composition tables, SSV, and SSM add/update/delete workflows
5. add explicit save/save-as and dirty-state handling
6. deepen parameter binding and resource editing only after the diagram command path is stable

## Definition of Success for the First Release

The first release is successful if a user can:

- open or create an SSP project
- import an FMU
- inspect its variables
- create the corresponding SSP component and connections
- save a valid SSP archive

If those flows are solid, the project will already be useful, and more advanced editing and visualization can be added on top without reworking the foundation.

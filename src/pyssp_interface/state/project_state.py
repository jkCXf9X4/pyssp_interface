from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ResourceSummary:
    name: str
    kind: str


@dataclass(slots=True)
class VariableSummary:
    name: str
    causality: str
    variability: str
    type_name: str
    description: str | None = None


@dataclass(slots=True)
class FMUSummary:
    resource_name: str
    model_name: str
    fmi_version: str
    variables: list[VariableSummary] = field(default_factory=list)


@dataclass(slots=True)
class ComponentSummary:
    name: str
    source: str | None
    component_type: str | None
    implementation: str | None
    connector_count: int


@dataclass(slots=True)
class ConnectorSummary:
    owner_path: str
    owner_name: str
    owner_kind: str
    name: str
    kind: str
    type_name: str | None = None


@dataclass(slots=True)
class ConnectionSummary:
    owner_path: str
    start_element: str | None
    start_connector: str
    end_element: str | None
    end_connector: str


@dataclass(slots=True)
class StructureNode:
    path: str
    node_kind: str
    name: str
    source: str | None = None
    component_type: str | None = None
    implementation: str | None = None
    connectors: list[ConnectorSummary] = field(default_factory=list)
    connections: list[ConnectionSummary] = field(default_factory=list)
    children: list["StructureNode"] = field(default_factory=list)


@dataclass(slots=True)
class ProjectSnapshot:
    project_path: Path
    project_name: str
    system_name: str | None = None
    structure_tree: StructureNode | None = None
    resources: list[ResourceSummary] = field(default_factory=list)
    fmus: list[FMUSummary] = field(default_factory=list)
    components: list[ComponentSummary] = field(default_factory=list)
    connectors: list[ConnectorSummary] = field(default_factory=list)
    connections: list[ConnectionSummary] = field(default_factory=list)
    validation_messages: list[str] = field(default_factory=list)
    dirty: bool = False

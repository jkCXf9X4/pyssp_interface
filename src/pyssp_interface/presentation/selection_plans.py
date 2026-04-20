from __future__ import annotations

from dataclasses import dataclass

from pyssp_interface.presentation.formatters import (
    format_component_summary,
    format_connection_summary,
    format_connector_summary,
    format_fmu_summary,
    format_project_summary,
    format_system_summary,
)
from pyssp_interface.presentation.resource_plans import build_resource_row_details
from pyssp_interface.state.project_index import (
    ComponentPayload,
    ConnectionPayload,
    ConnectorPayload,
    ProjectIndex,
)
from pyssp_interface.state.project_state import (
    ComponentSummary,
    ConnectionSummary,
    ConnectorSummary,
    FMUSummary,
    ProjectSnapshot,
    StructureNode,
)


@dataclass(slots=True)
class SelectionPlan:
    details_text: str | None = None
    explorer_tab: str = "details"
    structure_tab: str | None = None
    variables: list[FMUSummary] | None = None
    components: list[ComponentSummary] | None = None
    component_payloads: list[ComponentPayload] | None = None
    connectors: list[ConnectorSummary] | None = None
    connector_payloads: list[ConnectorPayload] | None = None
    connections: list[ConnectionSummary] | None = None
    connection_payloads: list[ConnectionPayload] | None = None
    render_diagram: bool = False
    diagram_node: StructureNode | None = None
    diagram_highlight_path: str | None = None
    clear_diagram_highlight: bool = False
    resource_view: tuple[str, str] | None = None


def build_tree_selection_plan(
    snapshot: ProjectSnapshot,
    index: ProjectIndex,
    payload: dict,
) -> SelectionPlan:
    kind = payload.get("kind", "unknown")

    if kind == "project":
        return SelectionPlan(
            details_text=format_project_summary(snapshot),
            variables=snapshot.fmus,
            components=snapshot.components,
            component_payloads=index.component_payloads(),
            connectors=snapshot.connectors,
            connector_payloads=index.connector_payloads(snapshot.connectors),
            connections=snapshot.connections,
            connection_payloads=index.connection_payloads(snapshot.connections),
            render_diagram=True,
            diagram_node=snapshot.structure_tree,
            diagram_highlight_path=snapshot.structure_tree.path if snapshot.structure_tree else None,
        )

    if kind == "resources":
        return SelectionPlan(
            details_text=f"{len(snapshot.resources)} resources",
            clear_diagram_highlight=True,
        )

    if kind == "resource":
        resource_name = payload.get("name")
        lowered = str(resource_name).lower()
        if lowered.endswith(".ssv"):
            return SelectionPlan(resource_view=("ssv", resource_name))
        if lowered.endswith(".ssm"):
            return SelectionPlan(resource_view=("ssm", resource_name))
        return SelectionPlan(
            details_text=payload.get("details", ""),
            clear_diagram_highlight=True,
        )

    if kind == "fmus":
        return SelectionPlan(
            details_text=f"{len(snapshot.fmus)} FMUs",
            explorer_tab="variables",
            variables=snapshot.fmus,
            render_diagram=True,
            diagram_node=snapshot.structure_tree,
        )

    if kind == "fmu":
        fmu = next(
            (item for item in snapshot.fmus if item.resource_name == payload.get("name")),
            None,
        )
        if fmu is None:
            return SelectionPlan()
        return SelectionPlan(
            details_text=format_fmu_summary(fmu),
            explorer_tab="variables",
            variables=[fmu],
            render_diagram=True,
            diagram_node=snapshot.structure_tree,
        )

    if kind == "component":
        node = index.find_structure_node(payload.get("path"))
        if node is None:
            return SelectionPlan()
        component = ComponentSummary(
            name=node.name,
            source=node.source,
            component_type=node.component_type,
            implementation=node.implementation,
            connector_count=len(node.connectors),
        )
        return SelectionPlan(
            details_text=format_component_summary(component),
            explorer_tab="structure",
            structure_tab="components",
            components=[component],
            component_payloads=[{"path": node.path}],
            connectors=node.connectors,
            connector_payloads=index.connector_payloads(node.connectors),
            render_diagram=True,
            diagram_node=index.find_parent_system(node.path),
            diagram_highlight_path=node.path,
        )

    if kind == "system":
        node = index.find_structure_node(payload.get("path"))
        if node is None:
            return SelectionPlan()
        return SelectionPlan(
            details_text=format_system_summary(node),
            explorer_tab="structure",
            structure_tab="connectors",
            connectors=node.connectors,
            connector_payloads=index.connector_payloads(node.connectors),
            connections=node.connections,
            connection_payloads=index.connection_payloads(node.connections),
            render_diagram=True,
            diagram_node=node,
            diagram_highlight_path=node.path,
        )

    if kind == "connectors":
        owner_path = payload.get("owner_path")
        node = index.find_structure_node(owner_path)
        connectors = node.connectors if node is not None else []
        return SelectionPlan(
            details_text=f"{len(connectors)} connectors in {payload.get('owner_name', '-')}",
            explorer_tab="structure",
            structure_tab="connectors",
            connectors=connectors,
            connector_payloads=index.connector_payloads(connectors),
            render_diagram=True,
            diagram_node=index.diagram_scope_for_path(owner_path),
            diagram_highlight_path=owner_path,
        )

    if kind == "connector":
        connector = index.find_connector(payload.get("owner_path"), payload.get("name"))
        if connector is None:
            return SelectionPlan()
        return SelectionPlan(
            details_text=format_connector_summary(connector),
            explorer_tab="structure",
            structure_tab="connectors",
            connectors=[connector],
            connector_payloads=index.connector_payloads([connector]),
            render_diagram=True,
            diagram_node=index.diagram_scope_for_path(payload.get("owner_path")),
            diagram_highlight_path=payload.get("owner_path"),
        )

    if kind == "connections":
        owner_path = payload.get("owner_path")
        node = index.find_structure_node(owner_path)
        connections = node.connections if node is not None else []
        return SelectionPlan(
            details_text=f"{len(connections)} connections in {payload.get('owner_name', '-')}",
            explorer_tab="structure",
            structure_tab="connections",
            connections=connections,
            connection_payloads=index.connection_payloads(connections),
            render_diagram=True,
            diagram_node=index.diagram_scope_for_path(owner_path),
            diagram_highlight_path=owner_path,
        )

    if kind == "connection":
        connection = index.find_connection(payload.get("owner_path"), payload.get("key"))
        if connection is None:
            return SelectionPlan()
        return SelectionPlan(
            details_text=format_connection_summary(connection),
            explorer_tab="structure",
            structure_tab="connections",
            connections=[connection],
            connection_payloads=[{"owner_path": connection.owner_path, "key": payload.get("key")}],
            render_diagram=True,
            diagram_node=index.find_structure_node(payload.get("owner_path")),
            diagram_highlight_path=payload.get("owner_path"),
        )

    return SelectionPlan()


def build_component_selection_plan(index: ProjectIndex, node: StructureNode | None) -> SelectionPlan:
    if node is None:
        return SelectionPlan()
    component = ComponentSummary(
        name=node.name,
        source=node.source,
        component_type=node.component_type,
        implementation=node.implementation,
        connector_count=len(node.connectors),
    )
    return SelectionPlan(
        details_text=format_component_summary(component),
        explorer_tab="structure",
        structure_tab="components",
        render_diagram=True,
        diagram_node=index.find_parent_system(node.path),
        diagram_highlight_path=node.path,
    )


def build_connector_selection_plan(index: ProjectIndex, connector: ConnectorSummary | None) -> SelectionPlan:
    if connector is None:
        return SelectionPlan()
    return SelectionPlan(
        details_text=format_connector_summary(connector),
        explorer_tab="structure",
        structure_tab="connectors",
        render_diagram=True,
        diagram_node=index.diagram_scope_for_path(connector.owner_path),
        diagram_highlight_path=connector.owner_path,
    )


def build_connection_selection_plan(index: ProjectIndex, connection: ConnectionSummary | None) -> SelectionPlan:
    if connection is None:
        return SelectionPlan()
    return SelectionPlan(
        details_text=format_connection_summary(connection),
        explorer_tab="structure",
        structure_tab="connections",
        render_diagram=True,
        diagram_node=index.find_structure_node(connection.owner_path),
        diagram_highlight_path=connection.owner_path,
    )


def build_resource_row_selection_plan(context: dict | None, payload: dict | None) -> SelectionPlan:
    details_text = build_resource_row_details(context, payload)
    if details_text is None:
        return SelectionPlan()
    return SelectionPlan(details_text=details_text, explorer_tab="resource")

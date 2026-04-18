from __future__ import annotations

from pyssp_interface.state.project_state import (
    ComponentSummary,
    ConnectionSummary,
    ConnectorSummary,
    FMUSummary,
    ProjectSnapshot,
    StructureNode,
)


def format_project_summary(snapshot: ProjectSnapshot) -> str:
    lines = [
        "Project",
        f"path: {snapshot.project_path}",
        f"system: {snapshot.system_name or '-'}",
        f"resources: {len(snapshot.resources)}",
        f"fmus: {len(snapshot.fmus)}",
        f"components: {len(snapshot.components)}",
        f"connectors: {len(snapshot.connectors)}",
        f"connections: {len(snapshot.connections)}",
        f"validation messages: {len(snapshot.validation_messages)}",
    ]
    if snapshot.structure_tree is not None:
        lines.extend(["", "SSD layout:", format_structure_outline(snapshot.structure_tree)])
    return "\n".join(lines)


def format_fmu_summary(fmu: FMUSummary) -> str:
    preview = "\n".join(
        f"- {variable.name} ({variable.causality}, {variable.type_name})"
        for variable in fmu.variables[:12]
    )
    if len(fmu.variables) > 12:
        preview += "\n- ..."

    return "\n".join(
        [
            "FMU",
            f"resource: {fmu.resource_name}",
            f"model name: {fmu.model_name}",
            f"FMI version: {fmu.fmi_version}",
            f"variable count: {len(fmu.variables)}",
            "variables:",
            preview or "- none",
        ]
    )


def format_component_summary(component: ComponentSummary) -> str:
    return "\n".join(
        [
            "Component",
            f"name: {component.name}",
            f"source: {component.source or '-'}",
            f"type: {component.component_type or '-'}",
            f"implementation: {component.implementation or '-'}",
            f"connectors: {component.connector_count}",
        ]
    )


def format_connector_summary(connector: ConnectorSummary) -> str:
    return "\n".join(
        [
            "Connector",
            f"owner: {connector.owner_name}",
            f"owner path: {connector.owner_path}",
            f"owner kind: {connector.owner_kind}",
            f"name: {connector.name}",
            f"kind: {connector.kind}",
            f"type: {connector.type_name or '-'}",
        ]
    )


def format_connection_summary(connection: ConnectionSummary) -> str:
    return "\n".join(
        [
            "Connection",
            f"owner path: {connection.owner_path}",
            f"source: {connection.start_element or '<system>'}.{connection.start_connector}",
            f"target: {connection.end_element or '<system>'}.{connection.end_connector}",
        ]
    )


def format_connection_line(connection: ConnectionSummary) -> str:
    return (
        f"{connection.start_element or '<system>'}.{connection.start_connector} -> "
        f"{connection.end_element or '<system>'}.{connection.end_connector}"
    )


def format_system_summary(node: StructureNode) -> str:
    return "\n".join(
        [
            "System",
            f"name: {node.name}",
            f"path: {node.path}",
            f"child nodes: {len(node.children)}",
            f"connectors: {len(node.connectors)}",
            f"connections: {len(node.connections)}",
        ]
    )


def format_structure_outline(node: StructureNode, depth: int = 0) -> str:
    indent = "  " * depth
    lines = [f"{indent}- {node.node_kind}: {node.name}"]
    for child in node.children:
        lines.append(format_structure_outline(child, depth + 1))
    return "\n".join(lines)

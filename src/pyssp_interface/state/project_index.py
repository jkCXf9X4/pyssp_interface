from __future__ import annotations

from typing import TypedDict

from pyssp_interface.state.project_state import (
    ConnectionSummary,
    ConnectorSummary,
    ProjectSnapshot,
    StructureNode,
)

ConnectionKey = tuple[str | None, str, str | None, str]


class ComponentPayload(TypedDict):
    path: str


class ConnectorPayload(TypedDict):
    owner_path: str
    name: str


class ConnectionPayload(TypedDict):
    owner_path: str
    key: ConnectionKey


class ProjectIndex:
    def __init__(self, snapshot: ProjectSnapshot | None):
        self.snapshot = snapshot

    def find_structure_node(self, path: str | None) -> StructureNode | None:
        if self.snapshot is None or self.snapshot.structure_tree is None or not path:
            return None

        def visit(node: StructureNode) -> StructureNode | None:
            if node.path == path:
                return node
            for child in node.children:
                found = visit(child)
                if found is not None:
                    return found
            return None

        return visit(self.snapshot.structure_tree)

    def find_parent_system(self, path: str | None) -> StructureNode | None:
        if self.snapshot is None or self.snapshot.structure_tree is None:
            return None
        if not path:
            return self.snapshot.structure_tree

        node = self.find_structure_node(path)
        if node is not None and node.node_kind == "system":
            return node

        parent_path = self.parent_path(path)
        if parent_path is None:
            return self.snapshot.structure_tree
        return self.find_structure_node(parent_path)

    def diagram_scope_for_path(self, path: str | None) -> StructureNode | None:
        node = self.find_structure_node(path)
        if node is not None and node.node_kind == "system":
            return node
        return self.find_parent_system(path)

    def find_connector(self, owner_path: str | None, name: str | None) -> ConnectorSummary | None:
        if self.snapshot is None or owner_path is None or name is None:
            return None
        return next(
            (
                item
                for item in self.snapshot.connectors
                if item.owner_path == owner_path and item.name == name
            ),
            None,
        )

    def find_connection(
        self,
        owner_path: str | None,
        key: ConnectionKey | None,
    ) -> ConnectionSummary | None:
        if self.snapshot is None or owner_path is None or key is None:
            return None
        return next(
            (
                item
                for item in self.snapshot.connections
                if item.owner_path == owner_path
                and (
                    item.start_element,
                    item.start_connector,
                    item.end_element,
                    item.end_connector,
                )
                == key
            ),
            None,
        )

    def component_payloads(self) -> list[ComponentPayload]:
        if self.snapshot is None or self.snapshot.structure_tree is None:
            return []

        payloads: list[ComponentPayload] = []

        def visit(node: StructureNode) -> None:
            for child in node.children:
                if child.node_kind == "component":
                    payloads.append({"path": child.path})
                visit(child)

        visit(self.snapshot.structure_tree)
        return payloads

    @staticmethod
    def connector_payloads(connectors: list[ConnectorSummary]) -> list[ConnectorPayload]:
        return [
            {"owner_path": connector.owner_path, "name": connector.name}
            for connector in connectors
        ]

    @staticmethod
    def connection_payloads(connections: list[ConnectionSummary]) -> list[ConnectionPayload]:
        return [
            {
                "owner_path": connection.owner_path,
                "key": (
                    connection.start_element,
                    connection.start_connector,
                    connection.end_element,
                    connection.end_connector,
                ),
            }
            for connection in connections
        ]

    def endpoint_pairs_for_system(self, system_path: str | None) -> list[tuple[str, str]]:
        node = self.find_structure_node(system_path)
        if node is None or node.node_kind != "system":
            return []

        endpoints = [(node.path, connector.name) for connector in node.connectors]
        for child in node.children:
            endpoints.extend((child.path, connector.name) for connector in child.connectors)
        return endpoints

    def root_system_path(self) -> str | None:
        if self.snapshot is None or self.snapshot.structure_tree is None:
            return None
        return self.snapshot.structure_tree.path

    @staticmethod
    def parent_path(path: str | None) -> str | None:
        if not path or "/" not in path:
            return None
        return path.rsplit("/", 1)[0]

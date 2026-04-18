from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from pyssp_interface.presentation.formatters import format_connection_line
from pyssp_interface.state.project_state import ProjectSnapshot, StructureNode


class ProjectTreeWidget(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setHeaderLabel("Project")

    def populate(self, snapshot: ProjectSnapshot) -> None:
        self.clear()

        root = QTreeWidgetItem([snapshot.project_name])
        root.setData(0, Qt.UserRole, {"kind": "project"})
        self.addTopLevelItem(root)

        resources_item = QTreeWidgetItem(["Resources"])
        resources_item.setData(0, Qt.UserRole, {"kind": "resources"})
        for resource in snapshot.resources:
            child = QTreeWidgetItem([resource.name])
            child.setData(
                0,
                Qt.UserRole,
                {
                    "kind": "resource",
                    "name": resource.name,
                    "details": f"Resource\nname: {resource.name}\nkind: {resource.kind}",
                },
            )
            resources_item.addChild(child)

        fmus_item = QTreeWidgetItem(["FMUs"])
        fmus_item.setData(0, Qt.UserRole, {"kind": "fmus"})
        for fmu in snapshot.fmus:
            child = QTreeWidgetItem([fmu.resource_name])
            child.setData(0, Qt.UserRole, {"kind": "fmu", "name": fmu.resource_name})
            fmus_item.addChild(child)

        root.addChild(resources_item)
        root.addChild(fmus_item)
        if snapshot.structure_tree is not None:
            root.addChild(self._build_structure_tree_item(snapshot.structure_tree))

        root.setExpanded(True)
        resources_item.setExpanded(True)
        fmus_item.setExpanded(True)
        self.setCurrentItem(root)

    def current_payload(self) -> dict:
        selected_items = self.selectedItems()
        if not selected_items:
            return {}
        return selected_items[0].data(0, Qt.UserRole) or {}

    def find_item_by_path(self, path: str) -> QTreeWidgetItem | None:
        for index in range(self.topLevelItemCount()):
            found = self._visit_tree_item(self.topLevelItem(index), path)
            if found is not None:
                return found
        return None

    def _visit_tree_item(self, item: QTreeWidgetItem, path: str) -> QTreeWidgetItem | None:
        payload = item.data(0, Qt.UserRole) or {}
        if payload.get("path") == path:
            return item
        for index in range(item.childCount()):
            found = self._visit_tree_item(item.child(index), path)
            if found is not None:
                return found
        return None

    def _build_structure_tree_item(self, node: StructureNode) -> QTreeWidgetItem:
        label = f"System: {node.name}" if node.node_kind == "system" else f"Component: {node.name}"
        item = QTreeWidgetItem([label])
        item.setData(
            0,
            Qt.UserRole,
            {
                "kind": node.node_kind,
                "path": node.path,
                "name": node.name,
            },
        )

        if node.connectors:
            connectors_item = QTreeWidgetItem(["Connectors"])
            connectors_item.setData(
                0,
                Qt.UserRole,
                {"kind": "connectors", "owner_path": node.path, "owner_name": node.name},
            )
            for connector in node.connectors:
                child = QTreeWidgetItem([f"{connector.name} [{connector.kind}]"])
                child.setData(
                    0,
                    Qt.UserRole,
                    {
                        "kind": "connector",
                        "owner_path": connector.owner_path,
                        "owner_name": connector.owner_name,
                        "name": connector.name,
                    },
                )
                connectors_item.addChild(child)
            item.addChild(connectors_item)

        for child_node in node.children:
            item.addChild(self._build_structure_tree_item(child_node))

        if node.connections:
            connections_item = QTreeWidgetItem(["Connections"])
            connections_item.setData(
                0,
                Qt.UserRole,
                {"kind": "connections", "owner_path": node.path, "owner_name": node.name},
            )
            for connection in node.connections:
                child = QTreeWidgetItem([format_connection_line(connection)])
                child.setData(
                    0,
                    Qt.UserRole,
                    {
                        "kind": "connection",
                        "owner_path": connection.owner_path,
                        "key": (
                            connection.start_element,
                            connection.start_connector,
                            connection.end_element,
                            connection.end_connector,
                        ),
                    },
                )
                connections_item.addChild(child)
            item.addChild(connections_item)

        item.setExpanded(True)
        return item

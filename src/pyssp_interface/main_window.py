from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
)

from pyssp_interface.services.project_service import SSPProjectService
from pyssp_interface.state.project_state import (
    ComponentSummary,
    ConnectionSummary,
    ConnectorSummary,
    FMUSummary,
    ProjectSnapshot,
    StructureNode,
)


class MainWindow(QMainWindow):
    def __init__(self, project_service: SSPProjectService | None = None):
        super().__init__()
        self.project_service = project_service or SSPProjectService()
        self.project: ProjectSnapshot | None = None
        self.repo_root = Path(__file__).resolve().parents[2]

        self.setWindowTitle("pyssp_interface")
        self.resize(1280, 780)

        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabel("Project")
        self.project_tree.itemSelectionChanged.connect(self._update_details)

        self.details_panel = QPlainTextEdit()
        self.details_panel.setReadOnly(True)
        self.details_panel.setPlaceholderText("Select a project item to inspect its details.")

        self.variable_table = self._create_table(
            ["FMU", "Name", "Causality", "Variability", "Type", "Description"]
        )
        self.component_table = self._create_table(
            ["Name", "Source", "Type", "Implementation", "Connectors"]
        )
        self.connector_table = self._create_table(
            ["Owner", "Owner Kind", "Name", "Kind", "Type"]
        )
        self.connection_table = self._create_table(
            ["Source Element", "Source Connector", "Target Element", "Target Connector"]
        )

        self.structure_tabs = QTabWidget()
        self.structure_tabs.addTab(self.component_table, "Components")
        self.structure_tabs.addTab(self.connector_table, "Connectors")
        self.structure_tabs.addTab(self.connection_table, "Connections")

        self.explorer_tabs = QTabWidget()
        self.explorer_tabs.addTab(self.details_panel, "Overview")
        self.explorer_tabs.addTab(self.variable_table, "Variables")
        self.explorer_tabs.addTab(self.structure_tabs, "Structure")

        self.validation_panel = QListWidget()

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self.explorer_tabs)
        right_splitter.addWidget(self.validation_panel)
        right_splitter.setSizes([560, 180])

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.project_tree)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([360, 920])
        self.setCentralWidget(main_splitter)

        self._build_menu()
        self.statusBar().showMessage("Ready")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        authoring_menu = self.menuBar().addMenu("&Authoring")
        sample_menu = self.menuBar().addMenu("&Samples")

        new_action = file_menu.addAction("New Project...")
        new_action.triggered.connect(self._new_project)

        open_action = file_menu.addAction("Open Project...")
        open_action.triggered.connect(self._open_project)

        import_action = file_menu.addAction("Import FMU...")
        import_action.triggered.connect(self._import_fmu)

        refresh_action = file_menu.addAction("Refresh")
        refresh_action.triggered.connect(self._refresh_project)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

        add_component_action = authoring_menu.addAction("Add Selected FMU As Component")
        add_component_action.triggered.connect(self._add_selected_fmu_as_component)
        add_system_connector_action = authoring_menu.addAction("Add System Connector...")
        add_system_connector_action.triggered.connect(self._add_system_connector)
        add_connection_action = authoring_menu.addAction("Add Connection...")
        add_connection_action.triggered.connect(self._add_connection)
        remove_connection_action = authoring_menu.addAction("Remove Selected Connection")
        remove_connection_action.triggered.connect(self._remove_selected_connection)

        embrace_action = sample_menu.addAction("Open Embrace Sample")
        embrace_action.triggered.connect(
            lambda: self._open_known_project(self.repo_root / "resources" / "embrace.ssp")
        )

        dcmotor_action = sample_menu.addAction("Open DCMotor Sample")
        dcmotor_action.triggered.connect(
            lambda: self._open_known_project(self.repo_root / "resources" / "dcmotor.ssp")
        )

    def _new_project(self) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Create SSP Project",
            str(Path.cwd() / "project.ssp"),
            "SSP archives (*.ssp)",
        )
        if not selected_path:
            return

        self._load_snapshot(self.project_service.create_project(selected_path))
        self.statusBar().showMessage(f"Created {selected_path}")

    def _open_project(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SSP Project",
            str(Path.cwd()),
            "SSP archives (*.ssp)",
        )
        if not selected_path:
            return

        self._load_snapshot(self.project_service.open_project(selected_path))
        self.statusBar().showMessage(f"Opened {selected_path}")

    def _import_fmu(self) -> None:
        if self.project is None:
            QMessageBox.information(self, "No project", "Create or open an SSP project first.")
            return

        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import FMU",
            str(Path.cwd()),
            "FMU files (*.fmu)",
        )
        if not selected_path:
            return

        self._load_snapshot(
            self.project_service.import_fmu(self.project.project_path, selected_path)
        )
        self.statusBar().showMessage(f"Imported {selected_path}")

    def _refresh_project(self) -> None:
        if self.project is None:
            return

        self._load_snapshot(self.project_service.open_project(self.project.project_path))
        self.statusBar().showMessage(f"Refreshed {self.project.project_path}")

    def _open_known_project(self, project_path: Path) -> None:
        self._load_snapshot(self.project_service.open_project(project_path))
        self.statusBar().showMessage(f"Opened {project_path}")

    def _add_selected_fmu_as_component(self) -> None:
        if self.project is None:
            QMessageBox.information(self, "No project", "Create or open an SSP project first.")
            return

        resource_name = self._selected_fmu_resource_name()
        if resource_name is None:
            QMessageBox.information(
                self,
                "No FMU selected",
                "Select an FMU under the FMUs or Resources section first.",
            )
            return

        try:
            snapshot = self.project_service.add_component_from_fmu(
                self.project.project_path,
                resource_name,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Add component failed", str(exc))
            return

        self._load_snapshot(snapshot)
        self.statusBar().showMessage(f"Added component from {resource_name}")

    def _add_system_connector(self) -> None:
        if self.project is None:
            QMessageBox.information(self, "No project", "Create or open an SSP project first.")
            return

        name, ok = QInputDialog.getText(self, "Add System Connector", "Connector name:")
        if not ok or not name.strip():
            return

        kind, ok = QInputDialog.getItem(
            self,
            "Add System Connector",
            "Connector kind:",
            ["input", "output", "parameter", "calculatedParameter"],
            editable=False,
        )
        if not ok:
            return

        type_name, ok = QInputDialog.getItem(
            self,
            "Add System Connector",
            "Connector type:",
            ["Real", "Integer", "Boolean", "String"],
            editable=False,
        )
        if not ok:
            return

        try:
            snapshot = self.project_service.add_system_connector(
                self.project.project_path,
                name=name,
                kind=kind,
                type_name=type_name,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Add connector failed", str(exc))
            return

        self._load_snapshot(snapshot)
        self.statusBar().showMessage(f"Added system connector {name}")

    def _add_connection(self) -> None:
        if self.project is None:
            QMessageBox.information(self, "No project", "Create or open an SSP project first.")
            return

        endpoint_items = self._connection_endpoint_items()
        if len(endpoint_items) < 2:
            QMessageBox.information(
                self,
                "Not enough connectors",
                "Add at least two connectors before creating a connection.",
            )
            return

        start_label, ok = QInputDialog.getItem(
            self,
            "Add Connection",
            "Start endpoint:",
            endpoint_items,
            editable=False,
        )
        if not ok:
            return

        end_label, ok = QInputDialog.getItem(
            self,
            "Add Connection",
            "End endpoint:",
            endpoint_items,
            editable=False,
        )
        if not ok:
            return

        start_element, start_connector = self._parse_endpoint_label(start_label)
        end_element, end_connector = self._parse_endpoint_label(end_label)
        if (start_element, start_connector) == (end_element, end_connector):
            QMessageBox.information(
                self,
                "Invalid connection",
                "Start and end endpoints must be different.",
            )
            return

        try:
            snapshot = self.project_service.add_connection(
                self.project.project_path,
                start_element=start_element,
                start_connector=start_connector,
                end_element=end_element,
                end_connector=end_connector,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Add connection failed", str(exc))
            return

        self._load_snapshot(snapshot)
        self.statusBar().showMessage("Added connection")

    def _remove_selected_connection(self) -> None:
        if self.project is None:
            QMessageBox.information(self, "No project", "Create or open an SSP project first.")
            return

        payload = self._current_tree_payload()
        if payload.get("kind") != "connection":
            QMessageBox.information(
                self,
                "No connection selected",
                "Select a connection in the project tree first.",
            )
            return

        start_element, start_connector, end_element, end_connector = payload["key"]
        try:
            snapshot = self.project_service.remove_connection(
                self.project.project_path,
                start_element=start_element,
                start_connector=start_connector,
                end_element=end_element,
                end_connector=end_connector,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Remove connection failed", str(exc))
            return

        self._load_snapshot(snapshot)
        self.statusBar().showMessage("Removed connection")

    def _load_snapshot(self, snapshot: ProjectSnapshot) -> None:
        self.project = snapshot
        self.setWindowTitle(f"pyssp_interface - {snapshot.project_name}")
        self._populate_tree(snapshot)
        self._populate_variables(snapshot.fmus)
        self._populate_structure(snapshot.components, snapshot.connectors, snapshot.connections)
        self._populate_validation(snapshot)
        self.details_panel.setPlainText(self._format_project_summary(snapshot))
        self.explorer_tabs.setCurrentWidget(self.details_panel)

    def _populate_tree(self, snapshot: ProjectSnapshot) -> None:
        self.project_tree.clear()

        root = QTreeWidgetItem([snapshot.project_name])
        root.setData(0, Qt.UserRole, {"kind": "project"})
        self.project_tree.addTopLevelItem(root)

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
            structure_root = self._build_structure_tree_item(snapshot.structure_tree)
            root.addChild(structure_root)
        root.setExpanded(True)
        for item in (resources_item, fmus_item):
            item.setExpanded(True)
        self.project_tree.setCurrentItem(root)

    def _build_structure_tree_item(self, node: StructureNode) -> QTreeWidgetItem:
        if node.node_kind == "system":
            label = f"System: {node.name}"
        else:
            label = f"Component: {node.name}"

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
                child = QTreeWidgetItem([self._format_connection_line(connection)])
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

    def _populate_validation(self, snapshot: ProjectSnapshot) -> None:
        self.validation_panel.clear()
        if snapshot.validation_messages:
            self.validation_panel.addItems(snapshot.validation_messages)
        else:
            self.validation_panel.addItem("No validation issues detected.")

    def _populate_variables(self, fmus: list[FMUSummary]) -> None:
        self._set_table_rows(
            self.variable_table,
            [
                [
                    fmu.resource_name,
                    variable.name,
                    variable.causality,
                    variable.variability,
                    variable.type_name,
                    variable.description or "",
                ]
                for fmu in fmus
                for variable in fmu.variables
            ],
        )

    def _populate_structure(
        self,
        components: list[ComponentSummary],
        connectors: list[ConnectorSummary],
        connections: list[ConnectionSummary],
    ) -> None:
        self._set_table_rows(
            self.component_table,
            [
                [
                    component.name,
                    component.source or "",
                    component.component_type or "",
                    component.implementation or "",
                    str(component.connector_count),
                ]
                for component in components
            ],
        )
        self._set_table_rows(
            self.connector_table,
            [
                [
                    connector.owner_name,
                    connector.owner_kind,
                    connector.name,
                    connector.kind,
                    connector.type_name or "",
                ]
                for connector in connectors
            ],
        )
        self._set_table_rows(
            self.connection_table,
            [
                [
                    connection.start_element or "<system>",
                    connection.start_connector,
                    connection.end_element or "<system>",
                    connection.end_connector,
                ]
                for connection in connections
            ],
        )

    def _update_details(self) -> None:
        selected_items = self.project_tree.selectedItems()
        if not selected_items or self.project is None:
            return

        payload = self._current_tree_payload()
        kind = payload.get("kind", "unknown")

        if kind == "project":
            self.details_panel.setPlainText(self._format_project_summary(self.project))
            self._populate_variables(self.project.fmus)
            self._populate_structure(
                self.project.components,
                self.project.connectors,
                self.project.connections,
            )
            self.explorer_tabs.setCurrentWidget(self.details_panel)
            return

        if kind == "resources":
            self.details_panel.setPlainText(f"{len(self.project.resources)} resources")
            self.explorer_tabs.setCurrentWidget(self.details_panel)
            return

        if kind == "resource":
            self.details_panel.setPlainText(payload.get("details", ""))
            self.explorer_tabs.setCurrentWidget(self.details_panel)
            return

        if kind == "fmus":
            self.details_panel.setPlainText(f"{len(self.project.fmus)} FMUs")
            self._populate_variables(self.project.fmus)
            self.explorer_tabs.setCurrentWidget(self.variable_table)
            return

        if kind == "fmu":
            fmu = next(
                (item for item in self.project.fmus if item.resource_name == payload.get("name")),
                None,
            )
            if fmu is not None:
                self.details_panel.setPlainText(self._format_fmu_summary(fmu))
                self._set_table_rows(
                    self.variable_table,
                    [
                        [
                            fmu.resource_name,
                            variable.name,
                            variable.causality,
                            variable.variability,
                            variable.type_name,
                            variable.description or "",
                        ]
                        for variable in fmu.variables
                    ],
                )
                self.explorer_tabs.setCurrentWidget(self.variable_table)
            return

        if kind == "components":
            self.details_panel.setPlainText(f"{len(self.project.components)} components")
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.component_table)
            return

        if kind == "component":
            node = self._find_structure_node(payload.get("path"))
            component = next((item for item in self.project.components if item.name == payload.get("name")), None)
            if component is not None and node is not None:
                self.details_panel.setPlainText(self._format_component_summary(component))
                self._set_table_rows(
                    self.component_table,
                    [[
                        component.name,
                        component.source or "",
                        component.component_type or "",
                        component.implementation or "",
                        str(component.connector_count),
                    ]],
                )
                self._set_table_rows(
                    self.connector_table,
                    [
                        [
                            connector.owner_name,
                            connector.owner_kind,
                            connector.name,
                            connector.kind,
                            connector.type_name or "",
                        ]
                        for connector in self.project.connectors
                        if connector.owner_path == node.path
                    ],
                )
                self.explorer_tabs.setCurrentWidget(self.structure_tabs)
                self.structure_tabs.setCurrentWidget(self.component_table)
            return

        if kind == "system":
            node = self._find_structure_node(payload.get("path"))
            if node is not None:
                self.details_panel.setPlainText(self._format_system_summary(node))
                self._set_table_rows(
                    self.connector_table,
                    [
                        [
                            connector.owner_name,
                            connector.owner_kind,
                            connector.name,
                            connector.kind,
                            connector.type_name or "",
                        ]
                        for connector in node.connectors
                    ],
                )
                self._set_table_rows(
                    self.connection_table,
                    [
                        [
                            connection.start_element or "<system>",
                            connection.start_connector,
                            connection.end_element or "<system>",
                            connection.end_connector,
                        ]
                        for connection in node.connections
                    ],
                )
                self.explorer_tabs.setCurrentWidget(self.structure_tabs)
                self.structure_tabs.setCurrentWidget(self.connector_table)
            return

        if kind == "connectors":
            owner_path = payload.get("owner_path")
            if owner_path:
                node = self._find_structure_node(owner_path)
                count = len(node.connectors) if node else 0
                self.details_panel.setPlainText(f"{count} connectors in {payload.get('owner_name')}")
                self._set_table_rows(
                    self.connector_table,
                    [
                        [
                            connector.owner_name,
                            connector.owner_kind,
                            connector.name,
                            connector.kind,
                            connector.type_name or "",
                        ]
                        for connector in (node.connectors if node else [])
                    ],
                )
            else:
                self.details_panel.setPlainText(f"{len(self.project.connectors)} connectors")
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.connector_table)
            return

        if kind == "connector":
            connector = next(
                (
                    item
                    for item in self.project.connectors
                    if item.owner_path == payload.get("owner_path")
                    and item.name == payload.get("name")
                ),
                None,
            )
            if connector is not None:
                self.details_panel.setPlainText(self._format_connector_summary(connector))
                self._set_table_rows(
                    self.connector_table,
                    [[
                        connector.owner_name,
                        connector.owner_kind,
                        connector.name,
                        connector.kind,
                        connector.type_name or "",
                    ]],
                )
                self.explorer_tabs.setCurrentWidget(self.structure_tabs)
                self.structure_tabs.setCurrentWidget(self.connector_table)
            return

        if kind == "connections":
            owner_path = payload.get("owner_path")
            if owner_path:
                node = self._find_structure_node(owner_path)
                count = len(node.connections) if node else 0
                self.details_panel.setPlainText(f"{count} connections in {payload.get('owner_name')}")
                self._set_table_rows(
                    self.connection_table,
                    [
                        [
                            connection.start_element or "<system>",
                            connection.start_connector,
                            connection.end_element or "<system>",
                            connection.end_connector,
                        ]
                        for connection in (node.connections if node else [])
                    ],
                )
            else:
                self.details_panel.setPlainText(f"{len(self.project.connections)} connections")
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.connection_table)
            return

        if kind == "connection":
            connection = next(
                (
                    item
                    for item in self.project.connections
                    if item.owner_path == payload.get("owner_path")
                    and (
                        item.start_element,
                        item.start_connector,
                        item.end_element,
                        item.end_connector,
                    )
                    == payload.get("key")
                ),
                None,
            )
            if connection is not None:
                self.details_panel.setPlainText(self._format_connection_summary(connection))
                self._set_table_rows(
                    self.connection_table,
                    [[
                        connection.start_element or "<system>",
                        connection.start_connector,
                        connection.end_element or "<system>",
                        connection.end_connector,
                    ]],
                )
                self.explorer_tabs.setCurrentWidget(self.structure_tabs)
                self.structure_tabs.setCurrentWidget(self.connection_table)

    @staticmethod
    def _create_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def _set_table_rows(table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        table.clearContents()
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                table.setItem(row_index, col_index, QTableWidgetItem(value))
        table.resizeColumnsToContents()

    def _selected_fmu_resource_name(self) -> str | None:
        payload = self._current_tree_payload()
        kind = payload.get("kind")
        if kind == "fmu":
            return payload.get("name")

        if kind == "resource" and str(payload.get("name", "")).lower().endswith(".fmu"):
            return payload.get("name")

        return None

    def _find_structure_node(self, path: str | None) -> StructureNode | None:
        if self.project is None or self.project.structure_tree is None or not path:
            return None

        def visit(node: StructureNode) -> StructureNode | None:
            if node.path == path:
                return node
            for child in node.children:
                found = visit(child)
                if found is not None:
                    return found
            return None

        return visit(self.project.structure_tree)

    def _connection_endpoint_items(self) -> list[str]:
        if self.project is None:
            return []

        return [
            self._format_endpoint_label(connector.owner_path, connector.name)
            for connector in self.project.connectors
        ]

    def _current_tree_payload(self) -> dict:
        selected_items = self.project_tree.selectedItems()
        if not selected_items:
            return {}
        return selected_items[0].data(0, Qt.UserRole) or {}

    @staticmethod
    def _format_endpoint_label(owner_path: str, connector_name: str) -> str:
        return f"{owner_path}.{connector_name}"

    @staticmethod
    def _parse_endpoint_label(label: str) -> tuple[str | None, str]:
        owner_name, connector_name = label.rsplit(".", 1)
        owner_name = owner_name.split("/")[-1]
        if owner_name in {"system", "<system>"}:
            return None, connector_name
        return owner_name, connector_name

    @staticmethod
    def _format_project_summary(snapshot: ProjectSnapshot) -> str:
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
            lines.extend(["", "SSD layout:", MainWindow._format_structure_outline(snapshot.structure_tree)])
        return "\n".join(lines)

    @staticmethod
    def _format_fmu_summary(fmu: FMUSummary) -> str:
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

    @staticmethod
    def _format_component_summary(component: ComponentSummary) -> str:
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

    @staticmethod
    def _format_connector_summary(connector: ConnectorSummary) -> str:
        return "\n".join(
            [
                "Connector",
                f"owner: {connector.owner_name}",
                f"owner kind: {connector.owner_kind}",
                f"name: {connector.name}",
                f"kind: {connector.kind}",
                f"type: {connector.type_name or '-'}",
            ]
        )

    @staticmethod
    def _format_connection_summary(connection: ConnectionSummary) -> str:
        return "\n".join(
            [
                "Connection",
                f"owner path: {connection.owner_path}",
                f"source: {connection.start_element or '<system>'}.{connection.start_connector}",
                f"target: {connection.end_element or '<system>'}.{connection.end_connector}",
            ]
        )

    @staticmethod
    def _format_connection_line(connection: ConnectionSummary) -> str:
        return (
            f"{connection.start_element or '<system>'}.{connection.start_connector} -> "
            f"{connection.end_element or '<system>'}.{connection.end_connector}"
        )

    @staticmethod
    def _format_system_summary(node: StructureNode) -> str:
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

    @staticmethod
    def _format_structure_outline(node: StructureNode, depth: int = 0) -> str:
        indent = "  " * depth
        label = f"{indent}- {node.node_kind}: {node.name}"
        lines = [label]
        for child in node.children:
            lines.append(MainWindow._format_structure_outline(child, depth + 1))
        return "\n".join(lines)

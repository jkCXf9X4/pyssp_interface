from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
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

        components_item = QTreeWidgetItem(["Components"])
        components_item.setData(0, Qt.UserRole, {"kind": "components"})
        for component in snapshot.components:
            child = QTreeWidgetItem([component.name])
            child.setData(0, Qt.UserRole, {"kind": "component", "name": component.name})
            components_item.addChild(child)

        connectors_item = QTreeWidgetItem(["Connectors"])
        connectors_item.setData(0, Qt.UserRole, {"kind": "connectors"})
        for connector in snapshot.connectors:
            label = f"{connector.owner_name}.{connector.name}"
            child = QTreeWidgetItem([label])
            child.setData(
                0,
                Qt.UserRole,
                {
                    "kind": "connector",
                    "owner_name": connector.owner_name,
                    "name": connector.name,
                },
            )
            connectors_item.addChild(child)

        connections_item = QTreeWidgetItem(["Connections"])
        connections_item.setData(0, Qt.UserRole, {"kind": "connections"})
        for connection in snapshot.connections:
            label = (
                f"{connection.start_element or '<system>'}.{connection.start_connector} -> "
                f"{connection.end_element or '<system>'}.{connection.end_connector}"
            )
            child = QTreeWidgetItem([label])
            child.setData(
                0,
                Qt.UserRole,
                {
                    "kind": "connection",
                    "key": (
                        connection.start_element,
                        connection.start_connector,
                        connection.end_element,
                        connection.end_connector,
                    ),
                },
            )
            connections_item.addChild(child)

        root.addChild(resources_item)
        root.addChild(fmus_item)
        root.addChild(components_item)
        root.addChild(connectors_item)
        root.addChild(connections_item)
        root.setExpanded(True)
        for item in (resources_item, fmus_item, components_item, connectors_item, connections_item):
            item.setExpanded(True)
        self.project_tree.setCurrentItem(root)

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

        payload = selected_items[0].data(0, Qt.UserRole) or {"kind": "unknown"}
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
            component = next(
                (item for item in self.project.components if item.name == payload.get("name")),
                None,
            )
            if component is not None:
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
                        if connector.owner_name == component.name
                    ],
                )
                self.explorer_tabs.setCurrentWidget(self.structure_tabs)
                self.structure_tabs.setCurrentWidget(self.component_table)
            return

        if kind == "connectors":
            self.details_panel.setPlainText(f"{len(self.project.connectors)} connectors")
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.connector_table)
            return

        if kind == "connector":
            connector = next(
                (
                    item
                    for item in self.project.connectors
                    if item.owner_name == payload.get("owner_name")
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
            self.details_panel.setPlainText(f"{len(self.project.connections)} connections")
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.connection_table)
            return

        if kind == "connection":
            connection = next(
                (
                    item
                    for item in self.project.connections
                    if (
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

    @staticmethod
    def _format_project_summary(snapshot: ProjectSnapshot) -> str:
        return "\n".join(
            [
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
        )

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
                f"source: {connection.start_element or '<system>'}.{connection.start_connector}",
                f"target: {connection.end_element or '<system>'}.{connection.end_connector}",
            ]
        )

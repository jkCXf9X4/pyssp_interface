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
)

from pyssp_interface.diagram_controller import DiagramController
from pyssp_interface.diagram_view import DiagramView
from pyssp_interface.presentation.formatters import (
    format_component_summary,
    format_connection_summary,
    format_connector_summary,
    format_fmu_summary,
    format_project_summary,
    format_system_summary,
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
from pyssp_interface.widgets.project_tree import ProjectTreeWidget


class MainWindow(QMainWindow):
    def __init__(self, project_service: SSPProjectService | None = None):
        super().__init__()
        self.project_service = project_service or SSPProjectService()
        self.project: ProjectSnapshot | None = None
        self.repo_root = Path(__file__).resolve().parents[2]
        self.diagram_controller = DiagramController()

        self.setWindowTitle("pyssp_interface")
        self.resize(1280, 780)

        self.project_tree = ProjectTreeWidget()
        self.project_tree.itemSelectionChanged.connect(self._update_details)

        self.details_panel = QPlainTextEdit()
        self.details_panel.setReadOnly(True)
        self.details_panel.setPlaceholderText("Select a project item to inspect its details.")

        self.diagram_view = DiagramView()
        self.diagram_view.pathActivated.connect(self._select_tree_path_from_diagram)
        self.diagram_view.blockMoved.connect(self._update_diagram_layout)
        self.diagram_view.endpointActivated.connect(self._handle_diagram_endpoint_activation)
        self.diagram_view.connectionActivated.connect(self._handle_diagram_connection_activation)

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
        self.explorer_tabs.addTab(self.diagram_view, "Diagram")
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
                system_path=self._current_system_scope_path(),
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
                system_path=self._current_system_scope_path(),
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
                "Add at least two connectors in the selected system scope before creating a connection.",
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

        start_owner_path, start_connector = self._parse_endpoint_label(start_label)
        end_owner_path, end_connector = self._parse_endpoint_label(end_label)
        if (start_owner_path, start_connector) == (end_owner_path, end_connector):
            QMessageBox.information(
                self,
                "Invalid connection",
                "Start and end endpoints must be different.",
            )
            return

        try:
            snapshot = self._create_connection_from_endpoints(
                start_owner_path=start_owner_path,
                start_connector=start_connector,
                end_owner_path=end_owner_path,
                end_connector=end_connector,
                system_path=self._current_system_scope_path(),
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

        connection = self._selected_connection_for_removal()
        if connection is None:
            QMessageBox.information(
                self,
                "No connection selected",
                "Select a connection in the project tree or diagram first.",
            )
            return

        try:
            snapshot = self.project_service.remove_connection(
                self.project.project_path,
                system_path=connection.owner_path,
                start_owner_path=self._connection_endpoint_owner_path(
                    connection.owner_path,
                    connection.start_element,
                ),
                start_element=None,
                start_connector=connection.start_connector,
                end_owner_path=self._connection_endpoint_owner_path(
                    connection.owner_path,
                    connection.end_element,
                ),
                end_element=None,
                end_connector=connection.end_connector,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Remove connection failed", str(exc))
            return

        self._load_snapshot(snapshot)
        self.statusBar().showMessage("Removed connection")

    def _load_snapshot(self, snapshot: ProjectSnapshot) -> None:
        self.project = snapshot
        self.diagram_controller.reset(snapshot.diagram_layouts)
        self.setWindowTitle(f"pyssp_interface - {snapshot.project_name}")
        self.project_tree.populate(snapshot)
        self._populate_variables(snapshot.fmus)
        self._populate_structure(snapshot.components, snapshot.connectors, snapshot.connections)
        self._populate_validation(snapshot)
        self.details_panel.setPlainText(format_project_summary(snapshot))
        self._render_diagram(
            snapshot.structure_tree,
            highlight_path=snapshot.structure_tree.path if snapshot.structure_tree else None,
        )
        self.explorer_tabs.setCurrentWidget(self.details_panel)

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
        self._set_table_rows(self.component_table, [self._component_row(component) for component in components])
        self._set_table_rows(self.connector_table, [self._connector_row(connector) for connector in connectors])
        self._set_table_rows(
            self.connection_table,
            [self._connection_row(connection) for connection in connections],
        )

    def _update_details(self) -> None:
        if self.project is None:
            return

        payload = self.project_tree.current_payload()
        kind = payload.get("kind", "unknown")

        if kind == "project":
            self.details_panel.setPlainText(format_project_summary(self.project))
            self._populate_variables(self.project.fmus)
            self._populate_structure(
                self.project.components,
                self.project.connectors,
                self.project.connections,
            )
            self._render_diagram(
                self.project.structure_tree,
                highlight_path=self.project.structure_tree.path if self.project.structure_tree else None,
            )
            self.explorer_tabs.setCurrentWidget(self.details_panel)
            return

        if kind == "resources":
            self.details_panel.setPlainText(f"{len(self.project.resources)} resources")
            self.diagram_view.set_highlighted_path(None)
            self.explorer_tabs.setCurrentWidget(self.details_panel)
            return

        if kind == "resource":
            self.details_panel.setPlainText(payload.get("details", ""))
            self.diagram_view.set_highlighted_path(None)
            self.explorer_tabs.setCurrentWidget(self.details_panel)
            return

        if kind == "fmus":
            self.details_panel.setPlainText(f"{len(self.project.fmus)} FMUs")
            self._populate_variables(self.project.fmus)
            self._render_diagram(self.project.structure_tree, highlight_path=None)
            self.explorer_tabs.setCurrentWidget(self.variable_table)
            return

        if kind == "fmu":
            fmu = next(
                (item for item in self.project.fmus if item.resource_name == payload.get("name")),
                None,
            )
            if fmu is None:
                return
            self.details_panel.setPlainText(format_fmu_summary(fmu))
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
            self._render_diagram(self.project.structure_tree, highlight_path=None)
            self.explorer_tabs.setCurrentWidget(self.variable_table)
            return

        if kind == "component":
            node = self._find_structure_node(payload.get("path"))
            if node is None:
                return
            component = ComponentSummary(
                name=node.name,
                source=node.source,
                component_type=node.component_type,
                implementation=node.implementation,
                connector_count=len(node.connectors),
            )
            self.details_panel.setPlainText(format_component_summary(component))
            self._set_table_rows(self.component_table, [self._component_row(component)])
            self._set_table_rows(
                self.connector_table,
                [self._connector_row(connector) for connector in node.connectors],
            )
            parent_system = self._find_parent_system(node.path)
            self._render_diagram(parent_system, highlight_path=node.path)
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.component_table)
            return

        if kind == "system":
            node = self._find_structure_node(payload.get("path"))
            if node is None:
                return
            self.details_panel.setPlainText(format_system_summary(node))
            self._set_table_rows(
                self.connector_table,
                [self._connector_row(connector) for connector in node.connectors],
            )
            self._set_table_rows(
                self.connection_table,
                [self._connection_row(connection) for connection in node.connections],
            )
            self._render_diagram(node, highlight_path=node.path)
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.connector_table)
            return

        if kind == "connectors":
            owner_path = payload.get("owner_path")
            node = self._find_structure_node(owner_path)
            connectors = node.connectors if node is not None else []
            self.details_panel.setPlainText(
                f"{len(connectors)} connectors in {payload.get('owner_name', '-')}"
            )
            self._set_table_rows(
                self.connector_table,
                [self._connector_row(connector) for connector in connectors],
            )
            self._render_diagram(self._diagram_scope_for_path(owner_path), highlight_path=owner_path)
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.connector_table)
            return

        if kind == "connector":
            connector = self._find_connector(payload.get("owner_path"), payload.get("name"))
            if connector is None:
                return
            self.details_panel.setPlainText(format_connector_summary(connector))
            self._set_table_rows(self.connector_table, [self._connector_row(connector)])
            self._render_diagram(
                self._diagram_scope_for_path(payload.get("owner_path")),
                highlight_path=payload.get("owner_path"),
            )
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.connector_table)
            return

        if kind == "connections":
            owner_path = payload.get("owner_path")
            node = self._find_structure_node(owner_path)
            connections = node.connections if node is not None else []
            self.details_panel.setPlainText(
                f"{len(connections)} connections in {payload.get('owner_name', '-')}"
            )
            self._set_table_rows(
                self.connection_table,
                [self._connection_row(connection) for connection in connections],
            )
            self._render_diagram(self._diagram_scope_for_path(owner_path), highlight_path=owner_path)
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.connection_table)
            return

        if kind == "connection":
            connection = self._find_connection(payload.get("owner_path"), payload.get("key"))
            if connection is None:
                return
            self.details_panel.setPlainText(format_connection_summary(connection))
            self._set_table_rows(self.connection_table, [self._connection_row(connection)])
            self._render_diagram(
                self._find_structure_node(payload.get("owner_path")),
                highlight_path=payload.get("owner_path"),
            )
            self.explorer_tabs.setCurrentWidget(self.structure_tabs)
            self.structure_tabs.setCurrentWidget(self.connection_table)

    def _selected_fmu_resource_name(self) -> str | None:
        payload = self.project_tree.current_payload()
        kind = payload.get("kind")
        if kind == "fmu":
            return payload.get("name")
        if kind == "resource" and str(payload.get("name", "")).lower().endswith(".fmu"):
            return payload.get("name")
        return None

    def _current_system_scope_path(self) -> str | None:
        payload = self.project_tree.current_payload()
        kind = payload.get("kind")
        root_path = self._root_system_path()
        if root_path is None:
            return None

        if kind == "system":
            return payload.get("path") or root_path
        if kind == "component":
            return self._parent_path(payload.get("path")) or root_path
        if kind in {"connectors", "connections"}:
            owner_path = payload.get("owner_path")
            node = self._find_structure_node(owner_path)
            if node is not None and node.node_kind == "system":
                return owner_path
            return self._parent_path(owner_path) or root_path
        if kind == "connector":
            owner_path = payload.get("owner_path")
            connector = self._find_connector(owner_path, payload.get("name"))
            if connector is not None and connector.owner_kind == "system":
                return owner_path
            return self._parent_path(owner_path) or root_path
        if kind == "connection":
            return payload.get("owner_path") or root_path
        return root_path

    def _connection_endpoint_items(self) -> list[str]:
        node = self._find_structure_node(self._current_system_scope_path())
        if node is None or node.node_kind != "system":
            return []

        labels = [
            self._format_endpoint_label(node.path, connector.name)
            for connector in node.connectors
        ]
        for child in node.children:
            labels.extend(
                self._format_endpoint_label(child.path, connector.name)
                for connector in child.connectors
            )
        return labels

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

    def _find_parent_system(self, path: str | None) -> StructureNode | None:
        if self.project is None or self.project.structure_tree is None:
            return None
        if not path:
            return self.project.structure_tree

        node = self._find_structure_node(path)
        if node is not None and node.node_kind == "system":
            return node

        parent_path = self._parent_path(path)
        return self._find_structure_node(parent_path) if parent_path else self.project.structure_tree

    def _diagram_scope_for_path(self, path: str | None) -> StructureNode | None:
        node = self._find_structure_node(path)
        if node is not None and node.node_kind == "system":
            return node
        return self._find_parent_system(path)

    def _find_connector(self, owner_path: str | None, name: str | None) -> ConnectorSummary | None:
        if self.project is None or owner_path is None or name is None:
            return None
        return next(
            (
                item
                for item in self.project.connectors
                if item.owner_path == owner_path and item.name == name
            ),
            None,
        )

    def _find_connection(
        self,
        owner_path: str | None,
        key: tuple[str | None, str, str | None, str] | None,
    ) -> ConnectionSummary | None:
        if self.project is None or owner_path is None or key is None:
            return None
        return next(
            (
                item
                for item in self.project.connections
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

    def _select_tree_path_from_diagram(self, path: str) -> None:
        item = self.project_tree.find_item_by_path(path)
        if item is None:
            return
        self.project_tree.setCurrentItem(item)
        self.explorer_tabs.setCurrentWidget(self.diagram_view)

    def _handle_diagram_endpoint_activation(self, owner_path: str, connector_name: str) -> None:
        if self.project is None:
            return

        self.diagram_view.set_selected_connection(None)
        system_path = self.diagram_view.current_system_path
        try:
            result = self.diagram_controller.activate_endpoint(
                owner_path=owner_path,
                connector_name=connector_name,
                system_path=system_path,
                create_connection=self._create_connection_from_endpoints,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Add connection failed", str(exc))
            self.diagram_view.set_selected_endpoint(self.diagram_controller.pending_endpoint)
            return

        self.diagram_view.set_selected_endpoint(self.diagram_controller.pending_endpoint)
        if result.message is not None:
            self.statusBar().showMessage(result.message)
        if result.snapshot is not None and system_path is not None:
            self._load_snapshot(result.snapshot)
            selected_system = self._find_structure_node(system_path)
            self._render_diagram(selected_system, highlight_path=system_path)

    def _handle_diagram_connection_activation(
        self,
        owner_path: str,
        key: tuple[str | None, str, str | None, str],
    ) -> None:
        connection = self._find_connection(owner_path, key)
        if connection is None:
            return
        message = self.diagram_controller.activate_connection(
            owner_path=owner_path,
            key=key,
            connection=connection,
        )
        self.diagram_view.set_selected_endpoint(None)
        self.diagram_view.set_selected_connection(self.diagram_controller.selected_connection)
        self.details_panel.setPlainText(format_connection_summary(connection))
        self._set_table_rows(self.connection_table, [self._connection_row(connection)])
        self.explorer_tabs.setCurrentWidget(self.diagram_view)
        if message is not None:
            self.statusBar().showMessage(message)

    def _update_diagram_layout(
        self,
        system_path: str,
        block_path: str,
        x: float,
        y: float,
    ) -> None:
        self.diagram_controller.update_block_position(
            system_path=system_path,
            block_path=block_path,
            x=x,
            y=y,
        )
        if self.project is not None:
            try:
                self.project_service.update_block_layout(
                    self.project.project_path,
                    system_path=system_path,
                    block_path=block_path,
                    x=x,
                    y=y,
                )
            except Exception as exc:
                QMessageBox.critical(self, "Persist layout failed", str(exc))
        current_node = self._find_structure_node(system_path)
        if current_node is None:
            return
        self._render_diagram(current_node, highlight_path=self._current_diagram_highlight_path())

    def _render_diagram(
        self,
        node: StructureNode | None,
        *,
        highlight_path: str | None,
    ) -> None:
        render_state = self.diagram_controller.render_state(node, highlighted_path=highlight_path)
        self.diagram_view.render_system(node, layout=render_state.layout)
        self.diagram_view.set_highlighted_path(render_state.highlighted_path)
        self.diagram_view.set_selected_endpoint(render_state.selected_endpoint)
        self.diagram_view.set_selected_connection(render_state.selected_connection)

    def _current_diagram_highlight_path(self) -> str | None:
        return self.project_tree.current_payload().get("path") or self.project_tree.current_payload().get(
            "owner_path"
        )

    def _root_system_path(self) -> str | None:
        if self.project is None or self.project.structure_tree is None:
            return None
        return self.project.structure_tree.path

    @staticmethod
    def _parent_path(path: str | None) -> str | None:
        if not path or "/" not in path:
            return None
        return path.rsplit("/", 1)[0]

    @staticmethod
    def _format_endpoint_label(owner_path: str, connector_name: str) -> str:
        return f"{owner_path}::{connector_name}"

    @staticmethod
    def _parse_endpoint_label(label: str) -> tuple[str, str]:
        owner_path, connector_name = label.rsplit("::", 1)
        return owner_path, connector_name

    @staticmethod
    def _connection_endpoint_owner_path(owner_system_path: str, local_element: str | None) -> str:
        if local_element is None:
            return owner_system_path
        return f"{owner_system_path}/{local_element}"

    def _create_connection_from_endpoints(
        self,
        *,
        start_owner_path: str,
        start_connector: str,
        end_owner_path: str,
        end_connector: str,
        system_path: str | None,
        ) -> ProjectSnapshot:
        if self.project is None:
            raise ValueError("No project is open")
        if (start_owner_path, start_connector) == (end_owner_path, end_connector):
            raise ValueError("Start and end endpoints must be different")
        return self.project_service.add_connection(
            self.project.project_path,
            system_path=system_path,
            start_owner_path=start_owner_path,
            start_element=None,
            start_connector=start_connector,
            end_owner_path=end_owner_path,
            end_element=None,
            end_connector=end_connector,
        )

    def _selected_connection_for_removal(self) -> ConnectionSummary | None:
        if self.diagram_controller.selected_connection is not None:
            owner_path, key = self.diagram_controller.selected_connection
            return self._find_connection(owner_path, key)

        payload = self.project_tree.current_payload()
        if payload.get("kind") != "connection":
            return None
        return self._find_connection(payload.get("owner_path"), payload.get("key"))

    @staticmethod
    def _component_row(component: ComponentSummary) -> list[str]:
        return [
            component.name,
            component.source or "",
            component.component_type or "",
            component.implementation or "",
            str(component.connector_count),
        ]

    @staticmethod
    def _connector_row(connector: ConnectorSummary) -> list[str]:
        return [
            connector.owner_name,
            connector.owner_kind,
            connector.name,
            connector.kind,
            connector.type_name or "",
        ]

    @staticmethod
    def _connection_row(connection: ConnectionSummary) -> list[str]:
        return [
            connection.start_element or "<system>",
            connection.start_connector,
            connection.end_element or "<system>",
            connection.end_connector,
        ]

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

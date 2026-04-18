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
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from pyssp_interface.services.project_service import SSPProjectService
from pyssp_interface.state.project_state import FMUSummary, ProjectSnapshot


class MainWindow(QMainWindow):
    def __init__(self, project_service: SSPProjectService | None = None):
        super().__init__()
        self.project_service = project_service or SSPProjectService()
        self.project: ProjectSnapshot | None = None

        self.setWindowTitle("pyssp_interface")
        self.resize(1200, 720)

        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabel("Project")
        self.project_tree.itemSelectionChanged.connect(self._update_details)

        self.details_panel = QPlainTextEdit()
        self.details_panel.setReadOnly(True)
        self.details_panel.setPlaceholderText("Select a project item to inspect its details.")

        self.validation_panel = QListWidget()

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self.details_panel)
        right_splitter.addWidget(self.validation_panel)
        right_splitter.setSizes([480, 180])

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.project_tree)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([360, 840])

        container = QWidget()
        self.setCentralWidget(main_splitter)

        self._build_menu()
        self.statusBar().showMessage("Ready")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

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

    def _load_snapshot(self, snapshot: ProjectSnapshot) -> None:
        self.project = snapshot
        self.setWindowTitle(f"pyssp_interface - {snapshot.project_name}")
        self._populate_tree(snapshot)
        self._populate_validation(snapshot)
        self.details_panel.setPlainText(self._format_project_summary(snapshot))

    def _populate_tree(self, snapshot: ProjectSnapshot) -> None:
        self.project_tree.clear()

        root = QTreeWidgetItem([snapshot.project_name])
        root.setData(0, Qt.UserRole, self._format_project_summary(snapshot))
        self.project_tree.addTopLevelItem(root)

        resources_item = QTreeWidgetItem(["Resources"])
        resources_item.setData(0, Qt.UserRole, f"{len(snapshot.resources)} resources")
        for resource in snapshot.resources:
            child = QTreeWidgetItem([resource.name])
            child.setData(0, Qt.UserRole, f"Resource\nname: {resource.name}\nkind: {resource.kind}")
            resources_item.addChild(child)

        fmus_item = QTreeWidgetItem(["FMUs"])
        fmus_item.setData(0, Qt.UserRole, f"{len(snapshot.fmus)} FMUs")
        for fmu in snapshot.fmus:
            child = QTreeWidgetItem([fmu.resource_name])
            child.setData(0, Qt.UserRole, self._format_fmu_summary(fmu))
            fmus_item.addChild(child)

        components_item = QTreeWidgetItem(["Components"])
        components_item.setData(0, Qt.UserRole, f"{len(snapshot.components)} components")
        for component in snapshot.components:
            details = "\n".join(
                [
                    "Component",
                    f"name: {component.name}",
                    f"source: {component.source or '-'}",
                    f"type: {component.component_type or '-'}",
                    f"implementation: {component.implementation or '-'}",
                    f"connectors: {component.connector_count}",
                ]
            )
            child = QTreeWidgetItem([component.name])
            child.setData(0, Qt.UserRole, details)
            components_item.addChild(child)

        connections_item = QTreeWidgetItem(["Connections"])
        connections_item.setData(0, Qt.UserRole, f"{len(snapshot.connections)} connections")
        for connection in snapshot.connections:
            label = (
                f"{connection.start_element or '<system>'}.{connection.start_connector} -> "
                f"{connection.end_element or '<system>'}.{connection.end_connector}"
            )
            child = QTreeWidgetItem([label])
            child.setData(0, Qt.UserRole, label)
            connections_item.addChild(child)

        root.addChild(resources_item)
        root.addChild(fmus_item)
        root.addChild(components_item)
        root.addChild(connections_item)
        root.setExpanded(True)
        for item in (resources_item, fmus_item, components_item, connections_item):
            item.setExpanded(True)

    def _populate_validation(self, snapshot: ProjectSnapshot) -> None:
        self.validation_panel.clear()
        if snapshot.validation_messages:
            self.validation_panel.addItems(snapshot.validation_messages)
        else:
            self.validation_panel.addItem("No validation issues detected.")

    def _update_details(self) -> None:
        selected_items = self.project_tree.selectedItems()
        if not selected_items:
            return

        details = selected_items[0].data(0, Qt.UserRole) or selected_items[0].text(0)
        self.details_panel.setPlainText(details)

    @staticmethod
    def _format_project_summary(snapshot: ProjectSnapshot) -> str:
        return "\n".join(
            [
                "Project",
                f"path: {snapshot.project_path}",
                f"resources: {len(snapshot.resources)}",
                f"fmus: {len(snapshot.fmus)}",
                f"components: {len(snapshot.components)}",
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


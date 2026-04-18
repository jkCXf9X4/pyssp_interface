from __future__ import annotations

from pathlib import Path

from pyssp_interface._vendor import ensure_vendor_paths
from pyssp_interface.state.project_state import (
    ComponentSummary,
    ConnectorSummary,
    ConnectionSummary,
    FMUSummary,
    ProjectSnapshot,
    ResourceSummary,
    VariableSummary,
)

ensure_vendor_paths()

from pyssp_standard.common_content_ssc import (
    TypeBoolean,
    TypeEnumeration,
    TypeInteger,
    TypeReal,
    TypeString,
)
from pyssp_standard.fmu import FMU
from pyssp_standard.ssd import Component, Connection, Connector, SSD, System
from pyssp_standard.ssp import SSP


class SSPProjectService:
    """Application-facing SSP operations built on top of pyssp_standard."""

    def create_project(self, project_path: Path | str) -> ProjectSnapshot:
        project_path = Path(project_path)
        project_path.parent.mkdir(parents=True, exist_ok=True)

        with SSP(project_path, mode="w") as ssp:
            with ssp.system_structure as ssd:
                ssd.name = project_path.stem
                ssd.version = "1.0"
                ssd.system = System(None, "system")

        return self.open_project(project_path)

    def open_project(self, project_path: Path | str) -> ProjectSnapshot:
        project_path = Path(project_path)
        if not project_path.exists():
            raise FileNotFoundError(project_path)

        resources: list[ResourceSummary] = []
        fmus: list[FMUSummary] = []
        components: list[ComponentSummary] = []
        connectors: list[ConnectorSummary] = []
        connections: list[ConnectionSummary] = []
        validation_messages: list[str] = []
        system_name: str | None = None

        with SSP(project_path, mode="r") as ssp:
            ssd = ssp.system_structure
            resources = [
                ResourceSummary(name=name, kind=self._resource_kind(name))
                for name in sorted(ssp.resources)
            ]
            fmus = self._load_fmus(ssp)

            if ssd.system is not None:
                system_name = ssd.system.name
                connectors = self._summarize_connectors(ssd)
                components = [
                    ComponentSummary(
                        name=element.name,
                        source=element.source,
                        component_type=element.component_type,
                        implementation=element.implementation,
                        connector_count=len(element.connectors),
                    )
                    for element in ssd.system.elements
                    if hasattr(element, "component_type")
                ]
                connections = [
                    ConnectionSummary(
                        start_element=connection.start_element,
                        start_connector=connection.start_connector,
                        end_element=connection.end_element,
                        end_connector=connection.end_connector,
                    )
                    for connection in ssd.connections()
                ]

                validation_messages.extend(ssd.check_connections())

            validation_messages.extend(self._validate_ssd(ssd))

        return ProjectSnapshot(
            project_path=project_path,
            project_name=project_path.name,
            system_name=system_name,
            resources=resources,
            fmus=fmus,
            components=components,
            connectors=connectors,
            connections=connections,
            validation_messages=validation_messages,
        )

    def import_fmu(
        self,
        project_path: Path | str,
        fmu_path: Path | str,
        *,
        overwrite: bool = False,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)
        fmu_path = Path(fmu_path)

        with SSP(project_path, mode="a") as ssp:
            ssp.add_resource(fmu_path, overwrite=overwrite)

        return self.open_project(project_path)

    def add_component_from_fmu(
        self,
        project_path: Path | str,
        resource_name: str,
        *,
        component_name: str | None = None,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)

        with SSP(project_path, mode="a") as ssp:
            resource_path = ssp.ssp_resource_path / resource_name
            if not resource_path.exists():
                raise FileNotFoundError(resource_name)
            if resource_path.suffix.lower() != ".fmu":
                raise ValueError(f"Resource is not an FMU: {resource_name}")

            with FMU(resource_path, mode="r") as fmu:
                model_description = fmu.model_description
                requested_name = component_name or model_description.model_name or Path(resource_name).stem
                connector_specs = [
                    (variable.name, variable.causality, variable.type_)
                    for variable in model_description.variables()
                    if variable.causality in {"input", "output", "parameter", "calculatedParameter"}
                ]

            with ssp.system_structure as ssd:
                if ssd.system is None:
                    ssd.system = System(None, "system")

                component_name = self._unique_component_name(requested_name, ssd)
                component = Component(None)
                component.name = component_name
                component.component_type = "application/x-fmu-sharedlibrary"
                component.source = str(Path("resources") / Path(resource_name).name)
                component.implementation = "CoSimulation"

                for connector_name, connector_kind, connector_type in connector_specs:
                    component.connectors.append(
                        Connector(None, connector_name, connector_kind, connector_type)
                    )
                    self._add_or_reuse_system_connector_and_connection(
                        ssd,
                        component_name=component_name,
                        connector_name=connector_name,
                        connector_kind=connector_kind,
                        connector_type=connector_type,
                    )

                ssd.system.elements.append(component)

        return self.open_project(project_path)

    def add_system_connector(
        self,
        project_path: Path | str,
        *,
        name: str,
        kind: str,
        type_name: str = "Real",
    ) -> ProjectSnapshot:
        project_path = Path(project_path)
        normalized_kind = kind.strip()
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Connector name is required")

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    ssd.system = System(None, "system")

                if any(existing.name == normalized_name for existing in ssd.system.connectors):
                    raise ValueError(f"System connector already exists: {normalized_name}")

                connector_type = self._make_type(type_name)
                ssd.system.connectors.append(
                    Connector(None, normalized_name, normalized_kind, connector_type)
                )

        return self.open_project(project_path)

    def add_connection(
        self,
        project_path: Path | str,
        *,
        start_element: str | None,
        start_connector: str,
        end_element: str | None,
        end_connector: str,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)
        connection = Connection(
            start_element=start_element,
            start_connector=start_connector,
            end_element=end_element,
            end_connector=end_connector,
        )

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")
                self._validate_connection_endpoints(ssd, connection)
                if connection in ssd.system.connections:
                    raise ValueError("Connection already exists")
                ssd.system.connections.append(connection)

        return self.open_project(project_path)

    def remove_connection(
        self,
        project_path: Path | str,
        *,
        start_element: str | None,
        start_connector: str,
        end_element: str | None,
        end_connector: str,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")

                connection = Connection(
                    start_element=start_element,
                    start_connector=start_connector,
                    end_element=end_element,
                    end_connector=end_connector,
                )
                if connection not in ssd.system.connections:
                    raise ValueError("Connection does not exist")
                ssd.system.connections.remove(connection)

        return self.open_project(project_path)

    def summarize_fmu(self, fmu_path: Path | str) -> FMUSummary:
        fmu_path = Path(fmu_path)
        with FMU(fmu_path, mode="r") as fmu:
            model_description = fmu.model_description
            variables = [
                VariableSummary(
                    name=variable.name,
                    causality=variable.causality,
                    variability=variable.variability,
                    type_name=type(variable.type_).__name__,
                    description=variable.description,
                )
                for variable in model_description.variables()
            ]

        return FMUSummary(
            resource_name=fmu_path.name,
            model_name=model_description.model_name,
            fmi_version=model_description.fmi_version,
            variables=variables,
        )

    def _load_fmus(self, ssp: SSP) -> list[FMUSummary]:
        summaries: list[FMUSummary] = []
        for resource_name in sorted(ssp.resources):
            if Path(resource_name).suffix.lower() != ".fmu":
                continue

            resource_path = ssp.ssp_resource_path / resource_name
            try:
                summaries.append(self.summarize_fmu(resource_path))
            except Exception as exc:
                summaries.append(
                    FMUSummary(
                        resource_name=resource_name,
                        model_name="<failed to read>",
                        fmi_version="unknown",
                        variables=[
                            VariableSummary(
                                name="<error>",
                                causality="unknown",
                                variability="unknown",
                                type_name=type(exc).__name__,
                                description=str(exc),
                            )
                        ],
                    )
                )

        return summaries

    def _validate_ssd(self, ssd: SSD) -> list[str]:
        try:
            ssd.__check_compliance__()
        except Exception as exc:
            return [f"SSD compliance check failed: {exc}"]
        return []

    def _validate_connection_endpoints(self, ssd: SSD, connection: Connection) -> None:
        valid_endpoints = {
            (None, connector.name)
            for connector in ssd.system.connectors
        }
        for element in ssd.system.elements:
            if not hasattr(element, "connectors"):
                continue
            valid_endpoints.update((element.name, connector.name) for connector in element.connectors)

        start = (connection.start_element, connection.start_connector)
        end = (connection.end_element, connection.end_connector)
        if start not in valid_endpoints:
            raise ValueError(
                f"Unknown start endpoint: {connection.start_element or '<system>'}.{connection.start_connector}"
            )
        if end not in valid_endpoints:
            raise ValueError(
                f"Unknown end endpoint: {connection.end_element or '<system>'}.{connection.end_connector}"
            )

    def _add_or_reuse_system_connector_and_connection(
        self,
        ssd: SSD,
        *,
        component_name: str,
        connector_name: str,
        connector_kind: str,
        connector_type,
    ) -> None:
        system_connector_name = self._choose_system_connector_name(
            ssd,
            component_name=component_name,
            connector_name=connector_name,
            connector_kind=connector_kind,
        )

        if not any(
            existing.name == system_connector_name and existing.kind == connector_kind
            for existing in ssd.system.connectors
        ):
            ssd.system.connectors.append(
                Connector(None, system_connector_name, connector_kind, connector_type)
            )

        if connector_kind in {"input", "parameter"}:
            connection = Connection(
                start_element=None,
                start_connector=system_connector_name,
                end_element=component_name,
                end_connector=connector_name,
            )
        elif connector_kind in {"output", "calculatedParameter"}:
            connection = Connection(
                start_element=component_name,
                start_connector=connector_name,
                end_element=None,
                end_connector=system_connector_name,
            )
        else:
            return

        if connection not in ssd.system.connections:
            ssd.system.connections.append(connection)

    def _choose_system_connector_name(
        self,
        ssd: SSD,
        *,
        component_name: str,
        connector_name: str,
        connector_kind: str,
    ) -> str:
        if not any(existing.name == connector_name for existing in ssd.system.connectors):
            return connector_name

        if any(
            existing.name == connector_name and existing.kind == connector_kind
            for existing in ssd.system.connectors
        ):
            return connector_name

        candidate = f"{component_name}.{connector_name}"
        existing_names = {existing.name for existing in ssd.system.connectors}
        if candidate not in existing_names:
            return candidate

        index = 2
        while True:
            candidate = f"{component_name}.{connector_name}_{index}"
            if candidate not in existing_names:
                return candidate
            index += 1

    @staticmethod
    def _unique_component_name(requested_name: str, ssd: SSD) -> str:
        existing_names = {
            element.name
            for element in ssd.system.elements
            if hasattr(element, "name") and element.name is not None
        }
        if requested_name not in existing_names:
            return requested_name

        index = 2
        while True:
            candidate = f"{requested_name}_{index}"
            if candidate not in existing_names:
                return candidate
            index += 1

    def _summarize_connectors(self, ssd: SSD) -> list[ConnectorSummary]:
        if ssd.system is None:
            return []

        summaries: list[ConnectorSummary] = []
        system_name = ssd.system.name or "<system>"

        for connector in ssd.system.connectors:
            summaries.append(
                ConnectorSummary(
                    owner_name=system_name,
                    owner_kind="system",
                    name=connector.name,
                    kind=connector.kind,
                    type_name=self._connector_type_name(connector),
                )
            )

        for element in ssd.system.elements:
            if not hasattr(element, "connectors"):
                continue

            owner_name = getattr(element, "name", "<unnamed>")
            owner_kind = "component" if hasattr(element, "component_type") else "system"
            for connector in element.connectors:
                summaries.append(
                    ConnectorSummary(
                        owner_name=owner_name,
                        owner_kind=owner_kind,
                        name=connector.name,
                        kind=connector.kind,
                        type_name=self._connector_type_name(connector),
                    )
                )

        return summaries

    @staticmethod
    def _resource_kind(resource_name: str) -> str:
        suffix = Path(resource_name).suffix.lower()
        if suffix:
            return suffix.removeprefix(".")
        return "file"

    @staticmethod
    def _connector_type_name(connector) -> str | None:
        type_obj = getattr(connector, "type_", None)
        if type_obj is None:
            return None
        return type(type_obj).__name__

    @staticmethod
    def _make_type(type_name: str):
        normalized = type_name.strip()
        if normalized == "Real":
            return TypeReal(None)
        if normalized == "Integer":
            return TypeInteger()
        if normalized == "Boolean":
            return TypeBoolean()
        if normalized == "String":
            return TypeString()
        if normalized.startswith("Enumeration:"):
            return TypeEnumeration(normalized.split(":", 1)[1].strip())
        raise ValueError(f"Unsupported connector type: {type_name}")

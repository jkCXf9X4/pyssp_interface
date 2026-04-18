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

from pyssp_standard.fmu import FMU
from pyssp_standard.ssd import SSD, System
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

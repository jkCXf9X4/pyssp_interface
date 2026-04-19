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
    SSMMappingSummary,
    SSVParameterSummary,
    StructureNode,
    VariableSummary,
)

ensure_vendor_paths()

from pyssp_standard.common_content_ssc import (
    Annotation,
    TypeBoolean,
    TypeEnumeration,
    TypeInteger,
    TypeReal,
    TypeString,
)
from pyssp_standard.fmu import FMU
from pyssp_standard.parameter_types import ParameterType
from pyssp_standard.ssm import SSM
from pyssp_standard.ssd import Component, Connection, Connector, SSD, System
from pyssp_standard.ssp import SSP
from pyssp_standard.ssv import SSV
from pyssp_standard.transformation_types import Transformation
from lxml import etree as ET
from lxml.etree import QName


class SSPProjectService:
    """Application-facing SSP operations built on top of pyssp_standard."""

    DIAGRAM_LAYOUT_ANNOTATION_TYPE = "pyssp_interface.diagram_layout"

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
        structure_tree: StructureNode | None = None
        diagram_layouts: dict[str, dict[str, tuple[float, float, float, float]]] = {}

        with SSP(project_path, mode="r") as ssp:
            ssd = ssp.system_structure
            resources = [
                ResourceSummary(name=name, kind=self._resource_kind(name))
                for name in sorted(ssp.resources)
            ]
            fmus = self._load_fmus(ssp)

            if ssd.system is not None:
                system_name = ssd.system.name
                structure_tree = self._build_structure_tree(ssd.system, path=ssd.system.name or "system")
                diagram_layouts = self._collect_diagram_layouts(
                    ssd.system,
                    path=ssd.system.name or "system",
                )
                components = self._flatten_components(structure_tree)
                connectors = self._flatten_connectors(structure_tree)
                connections = self._flatten_connections(structure_tree)

                validation_messages.extend(ssd.check_connections())

            validation_messages.extend(self._validate_ssd(ssd))

        return ProjectSnapshot(
            project_path=project_path,
            project_name=project_path.name,
            system_name=system_name,
            structure_tree=structure_tree,
            resources=resources,
            fmus=fmus,
            components=components,
            connectors=connectors,
            connections=connections,
            validation_messages=validation_messages,
            diagram_layouts=diagram_layouts,
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
        system_path: str | None = None,
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

                target_system_path, target_system = self._resolve_system_path_and_object(ssd, system_path)
                component_name = self._unique_component_name(requested_name, target_system)
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
                        target_system,
                        component_name=component_name,
                        connector_name=connector_name,
                        connector_kind=connector_kind,
                        connector_type=connector_type,
                    )

                target_system.elements.append(component)

        return self.open_project(project_path)

    def add_system_connector(
        self,
        project_path: Path | str,
        *,
        name: str,
        kind: str,
        type_name: str = "Real",
        system_path: str | None = None,
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

                _, target_system = self._resolve_system_path_and_object(ssd, system_path)

                if any(existing.name == normalized_name for existing in target_system.connectors):
                    raise ValueError(f"System connector already exists: {normalized_name}")

                connector_type = self._make_type(type_name)
                target_system.connectors.append(
                    Connector(None, normalized_name, normalized_kind, connector_type)
                )

        return self.open_project(project_path)

    def add_connection(
        self,
        project_path: Path | str,
        *,
        system_path: str | None = None,
        start_owner_path: str | None = None,
        start_element: str | None,
        start_connector: str,
        end_owner_path: str | None = None,
        end_element: str | None,
        end_connector: str,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")
                target_system_path, target_system = self._resolve_system_path_and_object(ssd, system_path)
                normalized_start_owner = self._normalize_owner_path(
                    target_system_path,
                    start_owner_path,
                    start_element,
                )
                normalized_end_owner = self._normalize_owner_path(
                    target_system_path,
                    end_owner_path,
                    end_element,
                )
                self._owner_path_to_local_element(target_system_path, normalized_start_owner)
                self._owner_path_to_local_element(target_system_path, normalized_end_owner)
                self._validate_connection_endpoints(
                    target_system,
                    target_system_path,
                    normalized_start_owner,
                    start_connector,
                    normalized_end_owner,
                    end_connector,
                )
                connection = Connection(
                    start_element=self._owner_path_to_local_element(target_system_path, normalized_start_owner),
                    start_connector=start_connector,
                    end_element=self._owner_path_to_local_element(target_system_path, normalized_end_owner),
                    end_connector=end_connector,
                )
                if connection in target_system.connections:
                    raise ValueError("Connection already exists")
                target_system.connections.append(connection)

        return self.open_project(project_path)

    def update_system_connector(
        self,
        project_path: Path | str,
        *,
        system_path: str | None = None,
        name: str,
        new_name: str,
        kind: str,
        type_name: str,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)
        normalized_name = new_name.strip()
        normalized_kind = kind.strip()
        if not normalized_name:
            raise ValueError("Connector name is required")

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    ssd.system = System(None, "system")

                _, target_system = self._resolve_system_path_and_object(ssd, system_path)
                connector = next((item for item in target_system.connectors if item.name == name), None)
                if connector is None:
                    raise ValueError(f"System connector does not exist: {name}")
                if any(item.name == normalized_name for item in target_system.connectors if item.name != name):
                    raise ValueError(f"System connector already exists: {normalized_name}")

                connector.name = normalized_name
                connector.kind = normalized_kind
                connector.type_ = self._make_type(type_name)

                for connection in target_system.connections:
                    if connection.start_element is None and connection.start_connector == name:
                        connection.start_connector = normalized_name
                    if connection.end_element is None and connection.end_connector == name:
                        connection.end_connector = normalized_name

        return self.open_project(project_path)

    def remove_system_connector(
        self,
        project_path: Path | str,
        *,
        system_path: str | None = None,
        name: str,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")

                _, target_system = self._resolve_system_path_and_object(ssd, system_path)
                connector = next((item for item in target_system.connectors if item.name == name), None)
                if connector is None:
                    raise ValueError(f"System connector does not exist: {name}")

                target_system.connectors.remove(connector)
                target_system.connections = [
                    connection
                    for connection in target_system.connections
                    if not (
                        (connection.start_element is None and connection.start_connector == name)
                        or (connection.end_element is None and connection.end_connector == name)
                    )
                ]

        return self.open_project(project_path)

    def remove_connection(
        self,
        project_path: Path | str,
        *,
        system_path: str | None = None,
        start_owner_path: str | None = None,
        start_element: str | None,
        start_connector: str,
        end_owner_path: str | None = None,
        end_element: str | None,
        end_connector: str,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")

                target_system_path, target_system = self._resolve_system_path_and_object(ssd, system_path)
                normalized_start_owner = self._normalize_owner_path(
                    target_system_path,
                    start_owner_path,
                    start_element,
                )
                normalized_end_owner = self._normalize_owner_path(
                    target_system_path,
                    end_owner_path,
                    end_element,
                )
                self._owner_path_to_local_element(target_system_path, normalized_start_owner)
                self._owner_path_to_local_element(target_system_path, normalized_end_owner)
                connection = Connection(
                    start_element=self._owner_path_to_local_element(target_system_path, normalized_start_owner),
                    start_connector=start_connector,
                    end_element=self._owner_path_to_local_element(target_system_path, normalized_end_owner),
                    end_connector=end_connector,
                )
                if connection not in target_system.connections:
                    raise ValueError("Connection does not exist")
                target_system.connections.remove(connection)

        return self.open_project(project_path)

    def remove_element(
        self,
        project_path: Path | str,
        *,
        element_path: str,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)
        system_path = self._parent_path(element_path)
        if system_path is None:
            raise ValueError(f"Cannot remove root element: {element_path}")

        element_name = element_path.rsplit("/", 1)[-1]

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")

                _, target_system = self._resolve_system_path_and_object(ssd, system_path)
                matching_elements = [
                    element
                    for element in target_system.elements
                    if getattr(element, "name", None) == element_name
                ]
                if not matching_elements:
                    raise ValueError(f"Element does not exist: {element_path}")

                target_system.elements.remove(matching_elements[0])
                target_system.connections = [
                    connection
                    for connection in target_system.connections
                    if connection.start_element != element_name and connection.end_element != element_name
                ]

        return self.open_project(project_path)

    def rename_element(
        self,
        project_path: Path | str,
        *,
        element_path: str,
        new_name: str,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)
        system_path = self._parent_path(element_path)
        if system_path is None:
            raise ValueError(f"Cannot rename root element: {element_path}")

        normalized_name = new_name.strip()
        if not normalized_name:
            raise ValueError("Element name is required")

        element_name = element_path.rsplit("/", 1)[-1]

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")

                _, target_system = self._resolve_system_path_and_object(ssd, system_path)
                matching_elements = [
                    element
                    for element in target_system.elements
                    if getattr(element, "name", None) == element_name
                ]
                if not matching_elements:
                    raise ValueError(f"Element does not exist: {element_path}")
                if any(
                    getattr(element, "name", None) == normalized_name
                    for element in target_system.elements
                    if getattr(element, "name", None) != element_name
                ):
                    raise ValueError(f"Element already exists: {normalized_name}")

                element = matching_elements[0]
                element.name = normalized_name
                for connection in target_system.connections:
                    if connection.start_element == element_name:
                        connection.start_element = normalized_name
                    if connection.end_element == element_name:
                        connection.end_element = normalized_name

                layouts = self._read_system_layout_annotation(target_system)
                old_layout_path = element_path
                new_layout_path = f"{system_path}/{normalized_name}"
                if old_layout_path in layouts:
                    layouts[new_layout_path] = layouts.pop(old_layout_path)
                    self._write_system_layout_annotation(target_system, layouts)

        return self.open_project(project_path)

    def update_component(
        self,
        project_path: Path | str,
        *,
        element_path: str,
        new_name: str,
        source: str | None,
        component_type: str | None,
        implementation: str | None,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)
        system_path = self._parent_path(element_path)
        if system_path is None:
            raise ValueError(f"Cannot update root element: {element_path}")

        normalized_name = new_name.strip()
        normalized_source = source.strip() if source is not None else ""
        normalized_component_type = component_type.strip() if component_type is not None else ""
        normalized_implementation = implementation.strip() if implementation is not None else ""
        if not normalized_name:
            raise ValueError("Element name is required")

        element_name = element_path.rsplit("/", 1)[-1]

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")

                _, target_system = self._resolve_system_path_and_object(ssd, system_path)
                element = next(
                    (
                        item
                        for item in target_system.elements
                        if getattr(item, "name", None) == element_name
                    ),
                    None,
                )
                if element is None:
                    raise ValueError(f"Element does not exist: {element_path}")
                if not isinstance(element, Component):
                    raise ValueError(f"Element is not a component: {element_path}")
                if any(
                    getattr(item, "name", None) == normalized_name
                    for item in target_system.elements
                    if getattr(item, "name", None) != element_name
                ):
                    raise ValueError(f"Element already exists: {normalized_name}")

                element.name = normalized_name
                element.source = normalized_source or None
                element.component_type = normalized_component_type or None
                element.implementation = normalized_implementation or None

                if normalized_name != element_name:
                    for connection in target_system.connections:
                        if connection.start_element == element_name:
                            connection.start_element = normalized_name
                        if connection.end_element == element_name:
                            connection.end_element = normalized_name

                    layouts = self._read_system_layout_annotation(target_system)
                    old_layout_path = element_path
                    new_layout_path = f"{system_path}/{normalized_name}"
                    if old_layout_path in layouts:
                        layouts[new_layout_path] = layouts.pop(old_layout_path)
                        self._write_system_layout_annotation(target_system, layouts)

        return self.open_project(project_path)

    def update_connection(
        self,
        project_path: Path | str,
        *,
        system_path: str | None = None,
        old_start_owner_path: str | None = None,
        old_start_element: str | None,
        old_start_connector: str,
        old_end_owner_path: str | None = None,
        old_end_element: str | None,
        old_end_connector: str,
        new_start_owner_path: str | None = None,
        new_start_element: str | None,
        new_start_connector: str,
        new_end_owner_path: str | None = None,
        new_end_element: str | None,
        new_end_connector: str,
    ) -> ProjectSnapshot:
        project_path = Path(project_path)

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")

                target_system_path, target_system = self._resolve_system_path_and_object(ssd, system_path)
                normalized_old_start_owner = self._normalize_owner_path(
                    target_system_path,
                    old_start_owner_path,
                    old_start_element,
                )
                normalized_old_end_owner = self._normalize_owner_path(
                    target_system_path,
                    old_end_owner_path,
                    old_end_element,
                )
                self._owner_path_to_local_element(target_system_path, normalized_old_start_owner)
                self._owner_path_to_local_element(target_system_path, normalized_old_end_owner)
                old_connection = Connection(
                    start_element=self._owner_path_to_local_element(
                        target_system_path,
                        normalized_old_start_owner,
                    ),
                    start_connector=old_start_connector,
                    end_element=self._owner_path_to_local_element(
                        target_system_path,
                        normalized_old_end_owner,
                    ),
                    end_connector=old_end_connector,
                )
                if old_connection not in target_system.connections:
                    raise ValueError("Connection does not exist")

                normalized_new_start_owner = self._normalize_owner_path(
                    target_system_path,
                    new_start_owner_path,
                    new_start_element,
                )
                normalized_new_end_owner = self._normalize_owner_path(
                    target_system_path,
                    new_end_owner_path,
                    new_end_element,
                )
                self._owner_path_to_local_element(target_system_path, normalized_new_start_owner)
                self._owner_path_to_local_element(target_system_path, normalized_new_end_owner)
                self._validate_connection_endpoints(
                    target_system,
                    target_system_path,
                    normalized_new_start_owner,
                    new_start_connector,
                    normalized_new_end_owner,
                    new_end_connector,
                )
                new_connection = Connection(
                    start_element=self._owner_path_to_local_element(
                        target_system_path,
                        normalized_new_start_owner,
                    ),
                    start_connector=new_start_connector,
                    end_element=self._owner_path_to_local_element(
                        target_system_path,
                        normalized_new_end_owner,
                    ),
                    end_connector=new_end_connector,
                )
                if new_connection != old_connection and new_connection in target_system.connections:
                    raise ValueError("Connection already exists")

                target_system.connections.remove(old_connection)
                target_system.connections.append(new_connection)

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

    def list_ssv_parameters(
        self,
        project_path: Path | str,
        *,
        resource_name: str,
    ) -> list[SSVParameterSummary]:
        project_path = Path(project_path)
        with SSP(project_path, mode="r") as ssp:
            resource_path = self._resource_temp_path(ssp, resource_name, suffix=".ssv")
            with SSV(resource_path, mode="r") as ssv:
                return [
                    SSVParameterSummary(
                        resource_name=resource_name,
                        name=parameter["name"],
                        type_name=parameter["type_name"],
                        value=parameter["type_value"].parameter.get("value"),
                    )
                    for parameter in ssv.parameters
                ]

    def add_ssv_parameter(
        self,
        project_path: Path | str,
        *,
        resource_name: str,
        name: str,
        type_name: str,
        value: str,
    ) -> list[SSVParameterSummary]:
        project_path = Path(project_path)
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Parameter name is required")

        with SSP(project_path, mode="a") as ssp:
            resource_path = self._resource_temp_path(ssp, resource_name, suffix=".ssv")
            with SSV(resource_path, mode="a") as ssv:
                if any(parameter["name"] == normalized_name for parameter in ssv.parameters):
                    raise ValueError(f"SSV parameter already exists: {normalized_name}")
                ssv.add_parameter(normalized_name, type_name, value=value)
            ssp.mark_changed()

        return self.list_ssv_parameters(project_path, resource_name=resource_name)

    def update_ssv_parameter(
        self,
        project_path: Path | str,
        *,
        resource_name: str,
        name: str,
        new_name: str,
        type_name: str,
        value: str,
    ) -> list[SSVParameterSummary]:
        project_path = Path(project_path)
        normalized_name = new_name.strip()
        if not normalized_name:
            raise ValueError("Parameter name is required")

        with SSP(project_path, mode="a") as ssp:
            resource_path = self._resource_temp_path(ssp, resource_name, suffix=".ssv")
            with SSV(resource_path, mode="a") as ssv:
                parameter = next((item for item in ssv.parameters if item["name"] == name), None)
                if parameter is None:
                    raise ValueError(f"SSV parameter does not exist: {name}")
                if any(item["name"] == normalized_name for item in ssv.parameters if item["name"] != name):
                    raise ValueError(f"SSV parameter already exists: {normalized_name}")
                parameter["name"] = normalized_name
                parameter["type_name"] = type_name
                parameter["type_value"] = ParameterType(type_name, {"value": value})
            ssp.mark_changed()

        return self.list_ssv_parameters(project_path, resource_name=resource_name)

    def remove_ssv_parameter(
        self,
        project_path: Path | str,
        *,
        resource_name: str,
        name: str,
    ) -> list[SSVParameterSummary]:
        project_path = Path(project_path)

        with SSP(project_path, mode="a") as ssp:
            resource_path = self._resource_temp_path(ssp, resource_name, suffix=".ssv")
            with SSV(resource_path, mode="a") as ssv:
                parameters = [item for item in ssv.parameters if item["name"] != name]
                if len(parameters) == len(ssv.parameters):
                    raise ValueError(f"SSV parameter does not exist: {name}")
                ssv.parameters = parameters
            ssp.mark_changed()

        return self.list_ssv_parameters(project_path, resource_name=resource_name)

    def list_ssm_mappings(
        self,
        project_path: Path | str,
        *,
        resource_name: str,
    ) -> list[SSMMappingSummary]:
        project_path = Path(project_path)
        with SSP(project_path, mode="r") as ssp:
            resource_path = self._resource_temp_path(ssp, resource_name, suffix=".ssm")
            with SSM(resource_path, "r") as ssm:
                return [
                    SSMMappingSummary(
                        resource_name=resource_name,
                        source=mapping["source"],
                        target=mapping["target"],
                        transformation_type=(
                            mapping["transformation"].transformation_type
                            if mapping["transformation"] is not None
                            else None
                        ),
                    )
                    for mapping in ssm.mappings
                ]

    def add_ssm_mapping(
        self,
        project_path: Path | str,
        *,
        resource_name: str,
        source: str,
        target: str,
    ) -> list[SSMMappingSummary]:
        project_path = Path(project_path)
        normalized_source = source.strip()
        normalized_target = target.strip()
        if not normalized_source or not normalized_target:
            raise ValueError("SSM source and target are required")

        with SSP(project_path, mode="a") as ssp:
            resource_path = self._resource_temp_path(ssp, resource_name, suffix=".ssm")
            with SSM(resource_path, "a") as ssm:
                if any(
                    mapping["source"] == normalized_source and mapping["target"] == normalized_target
                    for mapping in ssm.mappings
                ):
                    raise ValueError("SSM mapping already exists")
                ssm.add_mapping(normalized_source, normalized_target)
            ssp.mark_changed()

        return self.list_ssm_mappings(project_path, resource_name=resource_name)

    def update_ssm_mapping(
        self,
        project_path: Path | str,
        *,
        resource_name: str,
        source: str,
        target: str,
        new_source: str,
        new_target: str,
        transformation_type: str | None = None,
    ) -> list[SSMMappingSummary]:
        project_path = Path(project_path)
        normalized_source = new_source.strip()
        normalized_target = new_target.strip()
        if not normalized_source or not normalized_target:
            raise ValueError("SSM source and target are required")

        with SSP(project_path, mode="a") as ssp:
            resource_path = self._resource_temp_path(ssp, resource_name, suffix=".ssm")
            with SSM(resource_path, "a") as ssm:
                mapping = next(
                    (
                        item
                        for item in ssm.mappings
                        if item["source"] == source and item["target"] == target
                    ),
                    None,
                )
                if mapping is None:
                    raise ValueError("SSM mapping does not exist")
                if any(
                    item["source"] == normalized_source and item["target"] == normalized_target
                    for item in ssm.mappings
                    if not (item["source"] == source and item["target"] == target)
                ):
                    raise ValueError("SSM mapping already exists")
                mapping["source"] = normalized_source
                mapping["target"] = normalized_target
                mapping["transformation"] = self._make_transformation(transformation_type)
            ssp.mark_changed()

        return self.list_ssm_mappings(project_path, resource_name=resource_name)

    def remove_ssm_mapping(
        self,
        project_path: Path | str,
        *,
        resource_name: str,
        source: str,
        target: str,
    ) -> list[SSMMappingSummary]:
        project_path = Path(project_path)

        with SSP(project_path, mode="a") as ssp:
            resource_path = self._resource_temp_path(ssp, resource_name, suffix=".ssm")
            with SSM(resource_path, "a") as ssm:
                mappings = [
                    item
                    for item in ssm.mappings
                    if not (item["source"] == source and item["target"] == target)
                ]
                if len(mappings) == len(ssm.mappings):
                    raise ValueError("SSM mapping does not exist")
                ssm.mappings[:] = mappings
            ssp.mark_changed()

        return self.list_ssm_mappings(project_path, resource_name=resource_name)

    def update_block_layout(
        self,
        project_path: Path | str,
        *,
        system_path: str,
        block_path: str,
        x: float,
        y: float,
        width: float = 240.0,
        height: float = 84.0,
    ) -> None:
        project_path = Path(project_path)

        with SSP(project_path, mode="a") as ssp:
            with ssp.system_structure as ssd:
                if ssd.system is None:
                    raise ValueError("Project has no system structure")

                _, target_system = self._resolve_system_path_and_object(ssd, system_path)
                direct_child_paths = {
                    f"{system_path}/{getattr(element, 'name', '<unnamed>')}"
                    for element in target_system.elements
                    if hasattr(element, "name") and getattr(element, "name", None) is not None
                }
                if block_path not in direct_child_paths:
                    raise ValueError(f"Block {block_path} is not a direct child of system {system_path}")

                layouts = self._read_system_layout_annotation(target_system)
                layouts[block_path] = (x, y, width, height)
                self._write_system_layout_annotation(target_system, layouts)

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

    def _collect_diagram_layouts(
        self,
        system: System,
        *,
        path: str,
    ) -> dict[str, dict[str, tuple[float, float, float, float]]]:
        layouts: dict[str, dict[str, tuple[float, float, float, float]]] = {}
        system_layout = self._read_system_layout_annotation(system)
        if system_layout:
            layouts[path] = system_layout
        for element in system.elements:
            if isinstance(element, System):
                child_path = f"{path}/{element.name}"
                layouts.update(self._collect_diagram_layouts(element, path=child_path))
        return layouts

    def _read_system_layout_annotation(
        self,
        system: System,
    ) -> dict[str, tuple[float, float, float, float]]:
        annotation = self._find_layout_annotation(system)
        if annotation is None:
            return {}

        layouts: dict[str, tuple[float, float, float, float]] = {}
        for block in annotation.findall("block"):
            block_path = block.get("path")
            if not block_path:
                continue
            layouts[block_path] = (
                self._float_attr(block, "x", default=280.0),
                self._float_attr(block, "y", default=120.0),
                self._float_attr(block, "width", default=240.0),
                self._float_attr(block, "height", default=84.0),
            )
        return layouts

    def _write_system_layout_annotation(
        self,
        system: System,
        layouts: dict[str, tuple[float, float, float, float]],
    ) -> None:
        annotations_root = system.annotations.root
        for annotation in list(annotations_root):
            if annotation.get("type") == self.DIAGRAM_LAYOUT_ANNOTATION_TYPE:
                annotations_root.remove(annotation)

        annotation_element = ET.Element(
            QName(Annotation.namespaces["ssc"], "Annotation"),
            attrib={"type": self.DIAGRAM_LAYOUT_ANNOTATION_TYPE},
        )
        for block_path, geometry in sorted(layouts.items()):
            x, y, width, height = geometry
            annotation_element.append(
                ET.Element(
                    "block",
                    attrib={
                        "path": block_path,
                        "x": str(x),
                        "y": str(y),
                        "width": str(width),
                        "height": str(height),
                    },
                )
            )
        system.annotations.add_annotation(Annotation(annotation_element))

    def _find_layout_annotation(self, system: System):
        for annotation in system.annotations.root:
            if annotation.get("type") == self.DIAGRAM_LAYOUT_ANNOTATION_TYPE:
                return annotation
        return None

    @staticmethod
    def _float_attr(element, name: str, *, default: float) -> float:
        value = element.get(name)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def _validate_connection_endpoints(
        self,
        system: System,
        system_path: str,
        start_owner_path: str,
        start_connector: str,
        end_owner_path: str,
        end_connector: str,
    ) -> None:
        valid_endpoints = self._collect_valid_endpoints(system, system_path)

        start = (start_owner_path, start_connector)
        end = (end_owner_path, end_connector)
        if start not in valid_endpoints:
            raise ValueError(
                f"Unknown start endpoint: {start_owner_path}.{start_connector}"
            )
        if end not in valid_endpoints:
            raise ValueError(
                f"Unknown end endpoint: {end_owner_path}.{end_connector}"
            )

    def _collect_valid_endpoints(self, system: System, system_path: str) -> set[tuple[str, str]]:
        endpoints = {(system_path, connector.name) for connector in system.connectors}
        for element in system.elements:
            if hasattr(element, "connectors"):
                child_path = f"{system_path}/{element.name}"
                endpoints.update((child_path, connector.name) for connector in element.connectors)
        return endpoints

    def _add_or_reuse_system_connector_and_connection(
        self,
        target_system: System,
        *,
        component_name: str,
        connector_name: str,
        connector_kind: str,
        connector_type,
    ) -> None:
        system_connector_name = self._choose_system_connector_name(
            target_system,
            component_name=component_name,
            connector_name=connector_name,
            connector_kind=connector_kind,
        )

        if not any(
            existing.name == system_connector_name and existing.kind == connector_kind
            for existing in target_system.connectors
        ):
            target_system.connectors.append(
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

        if connection not in target_system.connections:
            target_system.connections.append(connection)

    def _choose_system_connector_name(
        self,
        target_system: System,
        *,
        component_name: str,
        connector_name: str,
        connector_kind: str,
    ) -> str:
        if not any(existing.name == connector_name for existing in target_system.connectors):
            return connector_name

        if any(
            existing.name == connector_name and existing.kind == connector_kind
            for existing in target_system.connectors
        ):
            return connector_name

        candidate = f"{component_name}.{connector_name}"
        existing_names = {existing.name for existing in target_system.connectors}
        if candidate not in existing_names:
            return candidate

        index = 2
        while True:
            candidate = f"{component_name}.{connector_name}_{index}"
            if candidate not in existing_names:
                return candidate
            index += 1

    @staticmethod
    def _unique_component_name(requested_name: str, target_system: System) -> str:
        existing_names = {
            element.name
            for element in target_system.elements
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

    def _resolve_system_path_and_object(
        self,
        ssd: SSD,
        system_path: str | None,
    ) -> tuple[str, System]:
        if ssd.system is None:
            raise ValueError("Project has no root system")

        root_path = ssd.system.name or "system"
        if system_path is None or system_path == root_path:
            return root_path, ssd.system

        found = self._find_system_by_path(ssd.system, current_path=root_path, target_path=system_path)
        if found is None:
            raise ValueError(f"Unknown system path: {system_path}")
        return system_path, found

    def _find_system_by_path(
        self,
        system: System,
        *,
        current_path: str,
        target_path: str,
    ) -> System | None:
        if current_path == target_path:
            return system
        for element in system.elements:
            if isinstance(element, System):
                child_path = f"{current_path}/{element.name}"
                found = self._find_system_by_path(
                    element,
                    current_path=child_path,
                    target_path=target_path,
                )
                if found is not None:
                    return found
        return None

    @staticmethod
    def _normalize_owner_path(
        system_path: str,
        owner_path: str | None,
        local_element: str | None,
    ) -> str:
        if owner_path:
            return owner_path
        if local_element is None:
            return system_path
        return f"{system_path}/{local_element}"

    @staticmethod
    def _owner_path_to_local_element(system_path: str, owner_path: str) -> str | None:
        if owner_path == system_path:
            return None
        prefix = f"{system_path}/"
        if owner_path.startswith(prefix):
            remainder = owner_path[len(prefix):]
            if "/" in remainder:
                raise ValueError(
                    f"Endpoint {owner_path} is not a direct child of system {system_path}"
                )
            return remainder
        raise ValueError(f"Endpoint {owner_path} is not inside system {system_path}")

    def _build_structure_tree(self, system: System, *, path: str) -> StructureNode:
        node = StructureNode(
            path=path,
            node_kind="system",
            name=system.name or "<system>",
        )

        node.connectors = [
            ConnectorSummary(
                owner_path=path,
                owner_name=node.name,
                owner_kind="system",
                name=connector.name,
                kind=connector.kind,
                type_name=self._connector_type_name(connector),
            )
            for connector in system.connectors
        ]
        node.connections = [
            ConnectionSummary(
                owner_path=path,
                start_element=connection.start_element,
                start_connector=connection.start_connector,
                end_element=connection.end_element,
                end_connector=connection.end_connector,
            )
            for connection in system.connections
        ]

        for element in system.elements:
            child_path = f"{path}/{getattr(element, 'name', '<unnamed>')}"
            if isinstance(element, System):
                node.children.append(self._build_structure_tree(element, path=child_path))
            elif isinstance(element, Component):
                node.children.append(
                    StructureNode(
                        path=child_path,
                        node_kind="component",
                        name=element.name or "<unnamed>",
                        source=element.source,
                        component_type=element.component_type,
                        implementation=element.implementation,
                        connectors=[
                            ConnectorSummary(
                                owner_path=child_path,
                                owner_name=element.name or "<unnamed>",
                                owner_kind="component",
                                name=connector.name,
                                kind=connector.kind,
                                type_name=self._connector_type_name(connector),
                            )
                            for connector in element.connectors
                        ],
                    )
                )

        return node

    def _flatten_components(self, node: StructureNode) -> list[ComponentSummary]:
        components: list[ComponentSummary] = []
        for child in node.children:
            if child.node_kind == "component":
                components.append(
                    ComponentSummary(
                        name=child.name,
                        source=child.source,
                        component_type=child.component_type,
                        implementation=child.implementation,
                        connector_count=len(child.connectors),
                    )
                )
            components.extend(self._flatten_components(child))
        return components

    def _flatten_connectors(self, node: StructureNode) -> list[ConnectorSummary]:
        connectors = list(node.connectors)
        for child in node.children:
            connectors.extend(self._flatten_connectors(child))
        return connectors

    def _flatten_connections(self, node: StructureNode) -> list[ConnectionSummary]:
        connections = list(node.connections)
        for child in node.children:
            connections.extend(self._flatten_connections(child))
        return connections

    @staticmethod
    def _resource_kind(resource_name: str) -> str:
        suffix = Path(resource_name).suffix.lower()
        if suffix:
            return suffix.removeprefix(".")
        return "file"

    @staticmethod
    def _resource_temp_path(ssp: SSP, resource_name: str, *, suffix: str) -> Path:
        resource_path = ssp.ssp_resource_path / resource_name
        if not resource_path.exists():
            raise FileNotFoundError(resource_name)
        if resource_path.suffix.lower() != suffix:
            raise ValueError(f"Resource is not a {suffix} file: {resource_name}")
        return resource_path

    @staticmethod
    def _parent_path(path: str | None) -> str | None:
        if not path or "/" not in path:
            return None
        return path.rsplit("/", 1)[0]

    @staticmethod
    def _connector_type_name(connector) -> str | None:
        type_obj = getattr(connector, "type_", None)
        if type_obj is None:
            return None
        return type(type_obj).__name__

    @staticmethod
    def _make_transformation(transformation_type: str | None) -> Transformation:
        normalized = (transformation_type or "").strip()
        if not normalized:
            return Transformation()

        attributes_by_type = {
            "LinearTransformation": {"factor": "1.0", "offset": "0.0"},
            "BooleanMappingTransformation": {"source": "false", "target": "false"},
            "IntegerMappingTransformation": {"source": "0", "target": "0"},
            "EnumerationMappingTransformation": {"source": "", "target": ""},
        }
        if normalized not in attributes_by_type:
            raise ValueError(f"Unsupported transformation type: {transformation_type}")
        return Transformation(normalized, attributes_by_type[normalized])

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

from __future__ import annotations

from pathlib import Path
import zipfile
import pytest

from pyssp_interface._vendor import ensure_vendor_paths
from pyssp_interface.services.project_service import SSPProjectService

ensure_vendor_paths()

from pyssp_standard.ssd import Component, Connector, System
from pyssp_standard.ssp import SSP


RESOURCE_ROOT = Path("resources")
EMBRACE_SSP = RESOURCE_ROOT / "embrace.ssp"
DCMOTOR_SSP = RESOURCE_ROOT / "dcmotor.ssp"


def _extract_fmu_from_ssp(ssp_path: Path, member_name: str, target_dir: Path) -> Path:
    with zipfile.ZipFile(ssp_path) as archive:
        archive.extract(member_name, path=target_dir)

    return target_dir / member_name


def test_create_project_creates_minimal_ssp(tmp_path):
    project_path = tmp_path / "demo.ssp"

    snapshot = SSPProjectService().create_project(project_path)

    assert project_path.exists()
    assert snapshot.project_path == project_path
    assert snapshot.project_name == "demo.ssp"
    assert snapshot.resources == []
    assert snapshot.components == []
    assert snapshot.connections == []


def test_open_project_reads_existing_fixture():
    snapshot = SSPProjectService().open_project(EMBRACE_SSP)

    assert snapshot.project_name == EMBRACE_SSP.name
    assert snapshot.resources
    assert snapshot.fmus
    assert snapshot.components
    assert snapshot.connectors
    assert snapshot.system_name


def test_open_project_reads_dcmotor_fixture():
    snapshot = SSPProjectService().open_project(DCMOTOR_SSP)

    assert snapshot.project_name == DCMOTOR_SSP.name
    assert len(snapshot.resources) == 3
    assert len(snapshot.fmus) == 3
    assert snapshot.components
    assert snapshot.connectors
    assert snapshot.structure_tree is not None
    assert snapshot.structure_tree.name == "DC-Motor"
    assert any(child.node_kind == "system" and child.name == "SuT" for child in snapshot.structure_tree.children)


def test_import_fmu_adds_resource_to_project(tmp_path):
    project_path = tmp_path / "import-demo.ssp"
    service = SSPProjectService()
    fmu_path = _extract_fmu_from_ssp(
        EMBRACE_SSP,
        "resources/0001_ECS_HW.fmu",
        tmp_path,
    )

    service.create_project(project_path)
    snapshot = service.import_fmu(project_path, fmu_path)

    assert any(resource.name == fmu_path.name for resource in snapshot.resources)
    assert any(fmu.resource_name == fmu_path.name for fmu in snapshot.fmus)


def test_add_component_from_imported_fmu_creates_structure(tmp_path):
    project_path = tmp_path / "authoring-demo.ssp"
    service = SSPProjectService()
    fmu_path = _extract_fmu_from_ssp(
        DCMOTOR_SSP,
        "resources/emachine_model.fmu",
        tmp_path,
    )

    service.create_project(project_path)
    service.import_fmu(project_path, fmu_path)
    snapshot = service.add_component_from_fmu(project_path, fmu_path.name)

    component = next((item for item in snapshot.components if item.source == f"resources/{fmu_path.name}"), None)
    assert component is not None
    assert component.connector_count > 0
    assert snapshot.connectors
    assert snapshot.connections


def test_add_system_connector_and_connection_round_trip(tmp_path):
    project_path = tmp_path / "connection-demo.ssp"
    service = SSPProjectService()

    service.create_project(project_path)
    snapshot = service.add_system_connector(
        project_path,
        name="driver_signal",
        kind="output",
        type_name="Real",
    )
    assert any(
        connector.owner_kind == "system" and connector.name == "driver_signal"
        for connector in snapshot.connectors
    )

    snapshot = service.add_system_connector(
        project_path,
        name="controller_input",
        kind="input",
        type_name="Real",
    )
    snapshot = service.add_connection(
        project_path,
        system_path="system",
        start_owner_path="system",
        start_element=None,
        start_connector="driver_signal",
        end_owner_path="system",
        end_element=None,
        end_connector="controller_input",
    )
    assert any(
        connection.start_element is None
        and connection.start_connector == "driver_signal"
        and connection.end_element is None
        and connection.end_connector == "controller_input"
        for connection in snapshot.connections
    )

    snapshot = service.remove_connection(
        project_path,
        system_path="system",
        start_owner_path="system",
        start_element=None,
        start_connector="driver_signal",
        end_owner_path="system",
        end_element=None,
        end_connector="controller_input",
    )
    assert not any(
        connection.start_element is None
        and connection.start_connector == "driver_signal"
        and connection.end_element is None
        and connection.end_connector == "controller_input"
        for connection in snapshot.connections
    )


def test_add_connection_rejects_duplicates(tmp_path):
    project_path = tmp_path / "duplicate-connection-demo.ssp"
    service = SSPProjectService()

    service.create_project(project_path)
    service.add_system_connector(project_path, name="driver_signal", kind="output", type_name="Real")
    service.add_system_connector(project_path, name="controller_input", kind="input", type_name="Real")
    service.add_connection(
        project_path,
        system_path="system",
        start_owner_path="system",
        start_element=None,
        start_connector="driver_signal",
        end_owner_path="system",
        end_element=None,
        end_connector="controller_input",
    )

    with pytest.raises(ValueError, match="Connection already exists"):
        service.add_connection(
            project_path,
            system_path="system",
            start_owner_path="system",
            start_element=None,
            start_connector="driver_signal",
            end_owner_path="system",
            end_element=None,
            end_connector="controller_input",
        )


def test_nested_authoring_targets_selected_subsystem(tmp_path):
    project_path = tmp_path / "nested-demo.ssp"
    service = SSPProjectService()
    root_path = "system"

    service.create_project(project_path)
    with SSP(project_path, mode="a") as ssp:
        with ssp.system_structure as ssd:
            nested = System(None, "SuT")
            component = Component(None)
            component.name = "emachine_model"
            component.component_type = "application/x-fmu-sharedlibrary"
            component.source = "resources/emachine_model.fmu"
            component.implementation = "CoSimulation"
            component.connectors.append(Connector(None, "U", "input"))
            nested.elements.append(component)
            ssd.system.elements.append(nested)

    snapshot = service.add_system_connector(
        project_path,
        system_path=f"{root_path}/SuT",
        name="nested_cmd",
        kind="input",
        type_name="Real",
    )
    assert any(
        connector.owner_path == f"{root_path}/SuT" and connector.name == "nested_cmd"
        for connector in snapshot.connectors
    )

    snapshot = service.add_connection(
        project_path,
        system_path=f"{root_path}/SuT",
        start_owner_path=f"{root_path}/SuT",
        start_element=None,
        start_connector="nested_cmd",
        end_owner_path=f"{root_path}/SuT/emachine_model",
        end_element=None,
        end_connector="U",
    )
    assert any(
        connection.owner_path == f"{root_path}/SuT"
        and connection.start_element is None
        and connection.start_connector == "nested_cmd"
        and connection.end_element == "emachine_model"
        and connection.end_connector == "U"
        for connection in snapshot.connections
    )


def test_add_connection_rejects_endpoints_outside_selected_system_scope(tmp_path):
    project_path = tmp_path / "invalid-nested-connection-demo.ssp"
    service = SSPProjectService()

    service.create_project(project_path)
    with SSP(project_path, mode="a") as ssp:
        with ssp.system_structure as ssd:
            nested = System(None, "SuT")
            component = Component(None)
            component.name = "emachine_model"
            component.connectors.append(Connector(None, "U", "input"))
            nested.elements.append(component)
            ssd.system.elements.append(nested)

    service.add_system_connector(
        project_path,
        system_path="system/SuT",
        name="nested_cmd",
        kind="input",
        type_name="Real",
    )

    with pytest.raises(ValueError, match="is not inside system system/SuT"):
        service.add_connection(
            project_path,
            system_path="system/SuT",
            start_owner_path="system",
            start_element=None,
            start_connector="nested_cmd",
            end_owner_path="system/SuT/emachine_model",
            end_element=None,
            end_connector="U",
        )


def test_update_block_layout_persists_per_system_scope(tmp_path):
    project_path = tmp_path / "layout-demo.ssp"
    service = SSPProjectService()

    service.create_project(project_path)
    with SSP(project_path, mode="a") as ssp:
        with ssp.system_structure as ssd:
            root_component = Component(None)
            root_component.name = "root_block"
            ssd.system.elements.append(root_component)

            nested = System(None, "SuT")
            nested_component = Component(None)
            nested_component.name = "nested_block"
            nested.elements.append(nested_component)
            ssd.system.elements.append(nested)

    service.update_block_layout(
        project_path,
        system_path="system",
        block_path="system/root_block",
        x=420.0,
        y=260.0,
    )
    service.update_block_layout(
        project_path,
        system_path="system/SuT",
        block_path="system/SuT/nested_block",
        x=560.0,
        y=310.0,
    )

    snapshot = service.open_project(project_path)

    assert snapshot.diagram_layouts["system"]["system/root_block"] == (420.0, 260.0, 240.0, 84.0)
    assert snapshot.diagram_layouts["system/SuT"]["system/SuT/nested_block"] == (
        560.0,
        310.0,
        240.0,
        84.0,
    )


def test_update_block_layout_overwrites_existing_geometry(tmp_path):
    project_path = tmp_path / "layout-overwrite-demo.ssp"
    service = SSPProjectService()

    service.create_project(project_path)
    with SSP(project_path, mode="a") as ssp:
        with ssp.system_structure as ssd:
            component = Component(None)
            component.name = "root_block"
            ssd.system.elements.append(component)

    service.update_block_layout(
        project_path,
        system_path="system",
        block_path="system/root_block",
        x=420.0,
        y=260.0,
    )
    service.update_block_layout(
        project_path,
        system_path="system",
        block_path="system/root_block",
        x=640.0,
        y=120.0,
        width=300.0,
        height=100.0,
    )

    snapshot = service.open_project(project_path)

    assert snapshot.diagram_layouts["system"]["system/root_block"] == (640.0, 120.0, 300.0, 100.0)


def test_update_block_layout_rejects_non_direct_children(tmp_path):
    project_path = tmp_path / "layout-invalid-target-demo.ssp"
    service = SSPProjectService()

    service.create_project(project_path)
    with SSP(project_path, mode="a") as ssp:
        with ssp.system_structure as ssd:
            nested = System(None, "SuT")
            nested_component = Component(None)
            nested_component.name = "nested_block"
            nested.elements.append(nested_component)
            ssd.system.elements.append(nested)

    with pytest.raises(ValueError, match="is not a direct child of system system"):
        service.update_block_layout(
            project_path,
            system_path="system",
            block_path="system/SuT/nested_block",
            x=420.0,
            y=260.0,
        )


def test_summarize_fmu_reads_fixture_metadata(tmp_path):
    fmu_path = _extract_fmu_from_ssp(
        DCMOTOR_SSP,
        "resources/emachine_model.fmu",
        tmp_path,
    )

    summary = SSPProjectService().summarize_fmu(fmu_path)

    assert summary.resource_name == fmu_path.name
    assert summary.model_name
    assert summary.fmi_version
    assert summary.variables

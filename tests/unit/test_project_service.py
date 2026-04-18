from __future__ import annotations

from pathlib import Path
import zipfile

from pyssp_interface.services.project_service import SSPProjectService


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
        start_element=None,
        start_connector="driver_signal",
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
        start_element=None,
        start_connector="driver_signal",
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

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

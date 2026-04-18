from __future__ import annotations

from pathlib import Path

from pyssp_interface.services.project_service import SSPProjectService


FIXTURE_ROOT = Path("3rd_party/pyssp_standard/pytest/doc/embrace")


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
    project_path = Path("3rd_party/pyssp_standard/pytest/doc/embrace.ssp")

    snapshot = SSPProjectService().open_project(project_path)

    assert snapshot.project_name == "embrace.ssp"
    assert snapshot.resources
    assert snapshot.fmus
    assert snapshot.components


def test_import_fmu_adds_resource_to_project(tmp_path):
    project_path = tmp_path / "import-demo.ssp"
    fmu_path = FIXTURE_ROOT / "resources/0001_ECS_HW.fmu"
    service = SSPProjectService()

    service.create_project(project_path)
    snapshot = service.import_fmu(project_path, fmu_path)

    assert any(resource.name == fmu_path.name for resource in snapshot.resources)
    assert any(fmu.resource_name == fmu_path.name for fmu in snapshot.fmus)


def test_summarize_fmu_reads_fixture_metadata():
    fmu_path = FIXTURE_ROOT / "resources/0001_ECS_HW.fmu"

    summary = SSPProjectService().summarize_fmu(fmu_path)

    assert summary.resource_name == fmu_path.name
    assert summary.model_name
    assert summary.fmi_version
    assert summary.variables

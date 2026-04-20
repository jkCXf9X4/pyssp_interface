from __future__ import annotations

from pathlib import Path

from pyssp_interface.resource_controller import (
    ResourceController,
    SSMMappingInput,
    SSVParameterInput,
)


class FakeProjectService:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def add_ssv_parameter(self, project_path, **kwargs):
        self.calls.append(("add_ssv_parameter", kwargs))
        return ["ssv-added"]

    def add_ssm_mapping(self, project_path, **kwargs):
        self.calls.append(("add_ssm_mapping", kwargs))
        return ["ssm-added"]

    def update_ssv_parameter(self, project_path, **kwargs):
        self.calls.append(("update_ssv_parameter", kwargs))
        return ["ssv-updated"]

    def update_ssm_mapping(self, project_path, **kwargs):
        self.calls.append(("update_ssm_mapping", kwargs))
        return ["ssm-updated"]

    def remove_ssv_parameter(self, project_path, **kwargs):
        self.calls.append(("remove_ssv_parameter", kwargs))
        return ["ssv-removed"]

    def remove_ssm_mapping(self, project_path, **kwargs):
        self.calls.append(("remove_ssm_mapping", kwargs))
        return ["ssm-removed"]


def test_add_row_for_ssv():
    controller = ResourceController()
    service = FakeProjectService()

    result = controller.add_row(
        project_service=service,
        project_path=Path("demo.ssp"),
        context={"resource_name": "params.ssv", "kind": "ssv"},
        value=SSVParameterInput(name="gain", type_name="Real", value="2.0"),
    )

    assert result.kind == "ssv"
    assert result.message == "Added SSV parameter gain"
    assert result.selection == ("gain",)
    assert service.calls[0][0] == "add_ssv_parameter"


def test_edit_row_for_ssm():
    controller = ResourceController()
    service = FakeProjectService()

    result = controller.edit_row(
        project_service=service,
        project_path=Path("demo.ssp"),
        context={"resource_name": "map.ssm", "kind": "ssm"},
        payload={"source": "a", "target": "b"},
        value=SSMMappingInput(source="c", target="d", transformation_type="linear"),
    )

    assert result.kind == "ssm"
    assert result.message == "Updated SSM mapping"
    assert result.selection == ("c", "d")
    assert service.calls[0][0] == "update_ssm_mapping"


def test_update_row_from_table_returns_none_when_unchanged():
    controller = ResourceController()
    service = FakeProjectService()

    result = controller.update_row_from_table(
        project_service=service,
        project_path=Path("demo.ssp"),
        context={"resource_name": "params.ssv", "kind": "ssv"},
        payload={"name": "gain", "type_name": "Real", "value": "2.0"},
        value=SSVParameterInput(name="gain", type_name="Real", value="2.0"),
    )

    assert result is None
    assert service.calls == []


def test_remove_row_for_ssm():
    controller = ResourceController()
    service = FakeProjectService()

    result = controller.remove_row(
        project_service=service,
        project_path=Path("demo.ssp"),
        context={"resource_name": "map.ssm", "kind": "ssm"},
        payload={"source": "a", "target": "b"},
    )

    assert result.kind == "ssm"
    assert result.message == "Removed SSM mapping"
    assert result.selection == ()
    assert service.calls[0][0] == "remove_ssm_mapping"

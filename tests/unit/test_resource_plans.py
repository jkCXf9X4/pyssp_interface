from __future__ import annotations

from pyssp_interface.presentation.resource_plans import (
    build_resource_row_details,
    build_ssm_resource_plan,
    build_ssv_resource_plan,
)
from pyssp_interface.state.project_state import SSMMappingSummary, SSVParameterSummary


def test_build_ssv_resource_plan():
    plan = build_ssv_resource_plan(
        "params.ssv",
        [SSVParameterSummary(resource_name="params.ssv", name="gain", type_name="Real", value="2.0")],
    )

    assert plan.kind == "ssv"
    assert plan.headers == ["Name", "Type", "Value"]
    assert plan.rows == [["gain", "Real", "2.0"]]
    assert plan.row_payloads == [{"name": "gain", "type_name": "Real", "value": "2.0"}]


def test_build_ssm_resource_plan():
    plan = build_ssm_resource_plan(
        "map.ssm",
        [SSMMappingSummary(resource_name="map.ssm", source="a", target="b", transformation_type="linear")],
    )

    assert plan.kind == "ssm"
    assert plan.headers == ["Source", "Target", "Transformation"]
    assert plan.rows == [["a", "b", "linear"]]
    assert plan.row_payloads == [{"source": "a", "target": "b", "transformation_type": "linear"}]


def test_build_resource_row_details_for_ssv_and_ssm():
    ssv_details = build_resource_row_details(
        {"resource_name": "params.ssv", "kind": "ssv"},
        {"name": "gain", "type_name": "Real", "value": "2.0"},
    )
    ssm_details = build_resource_row_details(
        {"resource_name": "map.ssm", "kind": "ssm"},
        {"source": "a", "target": "b", "transformation_type": "linear"},
    )

    assert "SSV Parameter" in ssv_details
    assert "gain" in ssv_details
    assert "SSM Mapping" in ssm_details
    assert "linear" in ssm_details

from __future__ import annotations

from dataclasses import dataclass

from pyssp_interface.state.project_state import SSMMappingSummary, SSVParameterSummary


@dataclass(slots=True)
class ResourceTablePlan:
    resource_name: str
    kind: str
    details_text: str
    headers: list[str]
    rows: list[list[str]]
    row_payloads: list[dict]
    editable_columns: set[int]


def build_ssv_resource_plan(
    resource_name: str,
    rows: list[SSVParameterSummary],
) -> ResourceTablePlan:
    return ResourceTablePlan(
        resource_name=resource_name,
        kind="ssv",
        details_text="\n".join(
            [
                "SSV Resource",
                f"resource: {resource_name}",
                f"parameters: {len(rows)}",
            ]
        ),
        headers=["Name", "Type", "Value"],
        rows=[[row.name, row.type_name, row.value or ""] for row in rows],
        row_payloads=[
            {"name": row.name, "type_name": row.type_name, "value": row.value}
            for row in rows
        ],
        editable_columns={0, 1, 2},
    )


def build_ssm_resource_plan(
    resource_name: str,
    rows: list[SSMMappingSummary],
) -> ResourceTablePlan:
    return ResourceTablePlan(
        resource_name=resource_name,
        kind="ssm",
        details_text="\n".join(
            [
                "SSM Resource",
                f"resource: {resource_name}",
                f"mappings: {len(rows)}",
            ]
        ),
        headers=["Source", "Target", "Transformation"],
        rows=[[row.source, row.target, row.transformation_type or ""] for row in rows],
        row_payloads=[
            {
                "source": row.source,
                "target": row.target,
                "transformation_type": row.transformation_type,
            }
            for row in rows
        ],
        editable_columns={0, 1, 2},
    )


def build_resource_row_details(context: dict | None, payload: dict | None) -> str | None:
    if context is None or payload is None:
        return None
    if context["kind"] == "ssv":
        return "\n".join(
            [
                "SSV Parameter",
                f"resource: {context['resource_name']}",
                f"name: {payload['name']}",
                f"type: {payload['type_name']}",
                f"value: {payload.get('value') or '-'}",
            ]
        )
    return "\n".join(
        [
            "SSM Mapping",
            f"resource: {context['resource_name']}",
            f"source: {payload['source']}",
            f"target: {payload['target']}",
            f"transformation: {payload.get('transformation_type') or '-'}",
        ]
    )

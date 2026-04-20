from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SSVParameterInput:
    name: str
    type_name: str
    value: str


@dataclass(slots=True)
class SSMMappingInput:
    source: str
    target: str
    transformation_type: str | None = None


@dataclass(slots=True)
class ResourceMutationResult:
    kind: str
    resource_name: str
    rows: list[Any]
    message: str
    selection: tuple[str, ...]


class ResourceController:
    def add_row(
        self,
        *,
        project_service,
        project_path: Path,
        context: dict,
        value: SSVParameterInput | SSMMappingInput,
    ) -> ResourceMutationResult:
        resource_name = context["resource_name"]
        if context["kind"] == "ssv":
            assert isinstance(value, SSVParameterInput)
            rows = project_service.add_ssv_parameter(
                project_path,
                resource_name=resource_name,
                name=value.name,
                type_name=value.type_name,
                value=value.value,
            )
            return ResourceMutationResult(
                kind="ssv",
                resource_name=resource_name,
                rows=rows,
                message=f"Added SSV parameter {value.name.strip()}",
                selection=(value.name.strip(),),
            )

        assert isinstance(value, SSMMappingInput)
        rows = project_service.add_ssm_mapping(
            project_path,
            resource_name=resource_name,
            source=value.source,
            target=value.target,
        )
        return ResourceMutationResult(
            kind="ssm",
            resource_name=resource_name,
            rows=rows,
            message="Added SSM mapping",
            selection=(value.source.strip(), value.target.strip()),
        )

    def edit_row(
        self,
        *,
        project_service,
        project_path: Path,
        context: dict,
        payload: dict,
        value: SSVParameterInput | SSMMappingInput,
    ) -> ResourceMutationResult:
        resource_name = context["resource_name"]
        if context["kind"] == "ssv":
            assert isinstance(value, SSVParameterInput)
            rows = project_service.update_ssv_parameter(
                project_path,
                resource_name=resource_name,
                name=payload["name"],
                new_name=value.name,
                type_name=value.type_name,
                value=value.value,
            )
            return ResourceMutationResult(
                kind="ssv",
                resource_name=resource_name,
                rows=rows,
                message=f"Updated SSV parameter {value.name.strip()}",
                selection=(value.name.strip(),),
            )

        assert isinstance(value, SSMMappingInput)
        rows = project_service.update_ssm_mapping(
            project_path,
            resource_name=resource_name,
            source=payload["source"],
            target=payload["target"],
            new_source=value.source,
            new_target=value.target,
            transformation_type=value.transformation_type,
        )
        return ResourceMutationResult(
            kind="ssm",
            resource_name=resource_name,
            rows=rows,
            message="Updated SSM mapping",
            selection=(value.source.strip(), value.target.strip()),
        )

    def remove_row(
        self,
        *,
        project_service,
        project_path: Path,
        context: dict,
        payload: dict,
    ) -> ResourceMutationResult:
        resource_name = context["resource_name"]
        if context["kind"] == "ssv":
            rows = project_service.remove_ssv_parameter(
                project_path,
                resource_name=resource_name,
                name=payload["name"],
            )
            return ResourceMutationResult(
                kind="ssv",
                resource_name=resource_name,
                rows=rows,
                message=f"Removed SSV parameter {payload['name']}",
                selection=(),
            )

        rows = project_service.remove_ssm_mapping(
            project_path,
            resource_name=resource_name,
            source=payload["source"],
            target=payload["target"],
        )
        return ResourceMutationResult(
            kind="ssm",
            resource_name=resource_name,
            rows=rows,
            message="Removed SSM mapping",
            selection=(),
        )

    def update_row_from_table(
        self,
        *,
        project_service,
        project_path: Path,
        context: dict,
        payload: dict,
        value: SSVParameterInput | SSMMappingInput,
    ) -> ResourceMutationResult | None:
        if context["kind"] == "ssv":
            assert isinstance(value, SSVParameterInput)
            if (
                value.name == payload["name"]
                and value.type_name == payload["type_name"]
                and value.value == (payload.get("value") or "")
            ):
                return None
        else:
            assert isinstance(value, SSMMappingInput)
            if (
                value.source == payload["source"]
                and value.target == payload["target"]
                and value.transformation_type == payload.get("transformation_type")
            ):
                return None
        return self.edit_row(
            project_service=project_service,
            project_path=project_path,
            context=context,
            payload=payload,
            value=value,
        )

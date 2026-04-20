from __future__ import annotations

from PySide6.QtWidgets import QInputDialog

from pyssp_interface.resource_controller import SSMMappingInput, SSVParameterInput


def prompt_add_resource_row(parent, context: dict) -> SSVParameterInput | SSMMappingInput | None:
    if context["kind"] == "ssv":
        name, ok = QInputDialog.getText(parent, "Add SSV Parameter", "Parameter name:")
        if not ok or not name.strip():
            return None
        type_name, ok = QInputDialog.getItem(
            parent,
            "Add SSV Parameter",
            "Parameter type:",
            ["Real", "Integer", "Boolean", "String"],
            editable=False,
        )
        if not ok:
            return None
        value, ok = QInputDialog.getText(parent, "Add SSV Parameter", "Value:")
        if not ok:
            return None
        return SSVParameterInput(name=name, type_name=type_name, value=value)

    source, ok = QInputDialog.getText(parent, "Add SSM Mapping", "Source:")
    if not ok or not source.strip():
        return None
    target, ok = QInputDialog.getText(parent, "Add SSM Mapping", "Target:")
    if not ok or not target.strip():
        return None
    return SSMMappingInput(source=source, target=target)


def prompt_edit_resource_row(parent, context: dict, payload: dict) -> SSVParameterInput | SSMMappingInput | None:
    if context["kind"] == "ssv":
        name, ok = QInputDialog.getText(
            parent,
            "Edit SSV Parameter",
            "Parameter name:",
            text=payload["name"],
        )
        if not ok or not name.strip():
            return None
        type_options = ["Real", "Integer", "Boolean", "String"]
        type_name, ok = QInputDialog.getItem(
            parent,
            "Edit SSV Parameter",
            "Parameter type:",
            type_options,
            type_options.index(payload["type_name"]) if payload["type_name"] in type_options else 0,
            editable=False,
        )
        if not ok:
            return None
        value, ok = QInputDialog.getText(
            parent,
            "Edit SSV Parameter",
            "Value:",
            text=payload.get("value", "") or "",
        )
        if not ok:
            return None
        return SSVParameterInput(name=name, type_name=type_name, value=value)

    source, ok = QInputDialog.getText(
        parent,
        "Edit SSM Mapping",
        "Source:",
        text=payload["source"],
    )
    if not ok or not source.strip():
        return None
    target, ok = QInputDialog.getText(
        parent,
        "Edit SSM Mapping",
        "Target:",
        text=payload["target"],
    )
    if not ok or not target.strip():
        return None
    transformation_type, ok = QInputDialog.getText(
        parent,
        "Edit SSM Mapping",
        "Transformation:",
        text=payload.get("transformation_type") or "",
    )
    if not ok:
        return None
    return SSMMappingInput(
        source=source,
        target=target,
        transformation_type=transformation_type.strip() or None,
    )

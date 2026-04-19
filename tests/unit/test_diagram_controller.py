from __future__ import annotations

from pathlib import Path

from pyssp_interface.diagram_controller import DiagramController
from pyssp_interface.state.project_state import ConnectionSummary, ProjectSnapshot, StructureNode


def _make_snapshot() -> ProjectSnapshot:
    return ProjectSnapshot(project_path=Path("demo.ssp"), project_name="demo.ssp")


def _make_system() -> StructureNode:
    return StructureNode(
        path="system",
        node_kind="system",
        name="system",
        children=[
            StructureNode(path="system/A", node_kind="component", name="A"),
            StructureNode(path="system/B", node_kind="component", name="B"),
        ],
    )


def test_activate_endpoint_tracks_selection_and_creates_connection():
    controller = DiagramController()
    created: list[tuple[str, str, str, str, str | None]] = []

    result = controller.activate_endpoint(
        owner_path="system/A",
        connector_name="y",
        system_path="system",
        create_connection=lambda **kwargs: created.append(
            (
                kwargs["start_owner_path"],
                kwargs["start_connector"],
                kwargs["end_owner_path"],
                kwargs["end_connector"],
                kwargs["system_path"],
            )
        )
        or _make_snapshot(),
    )

    assert result.status == "pending"
    assert controller.pending_endpoint == ("system/A", "y")

    result = controller.activate_endpoint(
        owner_path="system/B",
        connector_name="u",
        system_path="system",
        create_connection=lambda **kwargs: created.append(
            (
                kwargs["start_owner_path"],
                kwargs["start_connector"],
                kwargs["end_owner_path"],
                kwargs["end_connector"],
                kwargs["system_path"],
            )
        )
        or _make_snapshot(),
    )

    assert result.status == "created"
    assert result.snapshot is not None
    assert controller.pending_endpoint is None
    assert created == [("system/A", "y", "system/B", "u", "system")]


def test_activate_connection_clears_pending_endpoint_and_selects_connection():
    controller = DiagramController()
    controller.pending_endpoint = ("system/A", "y")
    connection = ConnectionSummary(
        owner_path="system",
        start_element="A",
        start_connector="y",
        end_element="B",
        end_connector="u",
    )
    key = ("A", "y", "B", "u")

    message = controller.activate_connection(
        owner_path="system",
        key=key,
        connection=connection,
    )

    assert controller.pending_endpoint is None
    assert controller.selected_connection == ("system", key)
    assert message == "Selected connection system: y -> u"


def test_render_state_clears_selections_outside_current_scope():
    controller = DiagramController()
    controller.pending_endpoint = ("other/A", "y")
    controller.selected_connection = ("other", ("A", "y", "B", "u"))

    render_state = controller.render_state(_make_system(), highlighted_path="system")

    assert render_state.selected_endpoint is None
    assert render_state.selected_connection is None
    assert render_state.highlighted_path == "system"

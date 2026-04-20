from __future__ import annotations

from pathlib import Path

from pyssp_interface.presentation.selection_plans import (
    build_component_selection_plan,
    build_tree_selection_plan,
)
from pyssp_interface.state.project_index import ProjectIndex
from pyssp_interface.state.project_state import (
    ComponentSummary,
    ConnectionSummary,
    ConnectorSummary,
    ProjectSnapshot,
    StructureNode,
)


def _snapshot() -> ProjectSnapshot:
    component_connector = ConnectorSummary(
        owner_path="root/plant",
        owner_name="plant",
        owner_kind="component",
        name="u",
        kind="input",
        type_name="TypeReal",
    )
    system_connector = ConnectorSummary(
        owner_path="root",
        owner_name="root",
        owner_kind="system",
        name="cmd",
        kind="input",
        type_name="TypeReal",
    )
    connection = ConnectionSummary(
        owner_path="root",
        start_element=None,
        start_connector="cmd",
        end_element="plant",
        end_connector="u",
    )
    structure_tree = StructureNode(
        path="root",
        node_kind="system",
        name="root",
        connectors=[system_connector],
        connections=[connection],
        children=[
            StructureNode(
                path="root/plant",
                node_kind="component",
                name="plant",
                source="resources/plant.fmu",
                component_type="application/x-fmu-sharedlibrary",
                implementation="CoSimulation",
                connectors=[component_connector],
            )
        ],
    )
    return ProjectSnapshot(
        project_path=Path("demo.ssp"),
        project_name="demo.ssp",
        system_name="root",
        structure_tree=structure_tree,
        components=[
            ComponentSummary(
                name="plant",
                source="resources/plant.fmu",
                component_type="application/x-fmu-sharedlibrary",
                implementation="CoSimulation",
                connector_count=1,
            )
        ],
        connectors=[system_connector, component_connector],
        connections=[connection],
    )


def test_tree_selection_plan_for_component_scopes_structure_and_diagram():
    snapshot = _snapshot()
    index = ProjectIndex(snapshot)

    plan = build_tree_selection_plan(snapshot, index, {"kind": "component", "path": "root/plant"})

    assert plan.explorer_tab == "structure"
    assert plan.structure_tab == "components"
    assert plan.diagram_node is snapshot.structure_tree
    assert plan.diagram_highlight_path == "root/plant"
    assert plan.components is not None
    assert plan.connectors is not None
    assert plan.component_payloads == [{"path": "root/plant"}]


def test_component_selection_plan_uses_parent_system_scope():
    snapshot = _snapshot()
    index = ProjectIndex(snapshot)
    node = index.find_structure_node("root/plant")

    plan = build_component_selection_plan(index, node)

    assert plan.explorer_tab == "structure"
    assert plan.structure_tab == "components"
    assert plan.diagram_node is snapshot.structure_tree
    assert plan.diagram_highlight_path == "root/plant"

from __future__ import annotations

from pyssp_interface.state.diagram_layout import DiagramLayoutStore
from pyssp_interface.state.project_state import StructureNode


def test_layout_store_seeds_updates_and_drops_blocks():
    node = StructureNode(
        path="root",
        node_kind="system",
        name="root",
        children=[
            StructureNode(path="root/A", node_kind="component", name="A"),
            StructureNode(path="root/B", node_kind="system", name="B"),
        ],
    )

    store = DiagramLayoutStore()
    layout = store.layout_for(node)

    assert layout is not None
    assert set(layout.blocks) == {"root/A", "root/B"}
    assert layout.blocks["root/A"].x == 280.0

    store.update_block_position("root", "root/A", x=420.0, y=260.0)
    layout = store.layout_for(node)
    assert layout.blocks["root/A"].x == 420.0
    assert layout.blocks["root/A"].y == 260.0

    updated_node = StructureNode(
        path="root",
        node_kind="system",
        name="root",
        children=[
            StructureNode(path="root/B", node_kind="system", name="B"),
        ],
    )
    layout = store.layout_for(updated_node)
    assert set(layout.blocks) == {"root/B"}

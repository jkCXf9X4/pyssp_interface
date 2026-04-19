from __future__ import annotations

from dataclasses import dataclass, field

from pyssp_interface.state.project_state import StructureNode


@dataclass(slots=True)
class BlockLayout:
    path: str
    x: float
    y: float
    width: float = 240.0
    height: float = 84.0


@dataclass(slots=True)
class SystemLayout:
    system_path: str
    blocks: dict[str, BlockLayout] = field(default_factory=dict)


class DiagramLayoutStore:
    def __init__(self):
        self._layouts: dict[str, SystemLayout] = {}

    def layout_for(self, node: StructureNode | None) -> SystemLayout | None:
        if node is None or node.node_kind != "system":
            return None
        layout = self._layouts.setdefault(node.path, SystemLayout(system_path=node.path))
        self._seed_missing_blocks(node, layout)
        self._drop_stale_blocks(node, layout)
        return layout

    def update_block_position(
        self,
        system_path: str,
        block_path: str,
        *,
        x: float,
        y: float,
    ) -> None:
        layout = self._layouts.setdefault(system_path, SystemLayout(system_path=system_path))
        block = layout.blocks.get(block_path)
        if block is None:
            layout.blocks[block_path] = BlockLayout(path=block_path, x=x, y=y)
            return
        block.x = x
        block.y = y

    @staticmethod
    def _seed_missing_blocks(node: StructureNode, layout: SystemLayout) -> None:
        center_x = 280.0
        top_y = 120.0
        block_gap = 34.0
        block_height = 84.0
        for index, child in enumerate(node.children):
            if child.path in layout.blocks:
                continue
            layout.blocks[child.path] = BlockLayout(
                path=child.path,
                x=center_x,
                y=top_y + index * (block_height + block_gap),
            )

    @staticmethod
    def _drop_stale_blocks(node: StructureNode, layout: SystemLayout) -> None:
        valid_paths = {child.path for child in node.children}
        stale_paths = [path for path in layout.blocks if path not in valid_paths]
        for path in stale_paths:
            del layout.blocks[path]

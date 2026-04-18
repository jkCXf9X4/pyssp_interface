from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from pyssp_interface.state.project_state import ConnectionSummary, ConnectorSummary, StructureNode


@dataclass(slots=True)
class _BlockGeometry:
    path: str
    rect: QRectF


class _SelectableRectItem(QGraphicsRectItem):
    def __init__(self, path: str, node_kind: str, rect: QRectF, on_activate):
        super().__init__(rect)
        self.path = path
        self.node_kind = node_kind
        self._on_activate = on_activate

    def mousePressEvent(self, event):
        self._on_activate(self.path)
        super().mousePressEvent(event)


class DiagramView(QGraphicsView):
    pathActivated = Signal(str)

    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setBackgroundBrush(QBrush(QColor("#f7f6f1")))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self._item_by_path: dict[str, _SelectableRectItem] = {}
        self._highlighted_path: str | None = None
        self._current_system_path: str | None = None

    def render_system(self, node: StructureNode | None) -> None:
        self._scene.clear()
        self._item_by_path.clear()
        self._current_system_path = None
        if node is None:
            self._scene.addText("Select a system to view its block diagram.")
            return

        self._current_system_path = node.path
        title = self._scene.addText(f"System Diagram: {node.name}")
        title.setPos(20, 20)

        if node.node_kind != "system":
            self._scene.addText("Diagram view is available at system scope only.").setPos(20, 50)
            return

        if not node.children and not node.connectors:
            self._scene.addText("System has no blocks or connectors to display.").setPos(20, 50)
            return

        left_connectors = [c for c in node.connectors if c.kind in {"input", "parameter"}]
        right_connectors = [c for c in node.connectors if c.kind in {"output", "calculatedParameter"}]
        other_connectors = [c for c in node.connectors if c.kind not in {"input", "parameter", "output", "calculatedParameter"}]

        system_left_x = 40
        system_right_x = 980
        center_x = 280
        top_y = 120
        block_width = 240
        block_height = 84
        block_gap = 34

        block_geometries: dict[str, _BlockGeometry] = {}

        self._draw_system_connector_column(left_connectors, system_left_x, top_y, align_right=False)
        self._draw_system_connector_column(right_connectors, system_right_x, top_y, align_right=True)
        self._draw_system_connector_column(other_connectors, 40, top_y + 320, align_right=False)

        for index, child in enumerate(node.children):
            y = top_y + index * (block_height + block_gap)
            rect = QRectF(center_x, y, block_width, block_height)
            self._draw_block(child, rect)
            block_geometries[child.path] = _BlockGeometry(path=child.path, rect=rect)

        for connection in node.connections:
            self._draw_connection(
                connection,
                node=node,
                block_geometries=block_geometries,
                system_left_x=system_left_x,
                system_right_x=system_right_x,
            )

        bounds = self._scene.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        self.setSceneRect(bounds)
        self.fitInView(bounds, Qt.KeepAspectRatio)
        self.set_highlighted_path(self._highlighted_path)

    def set_highlighted_path(self, path: str | None) -> None:
        self._highlighted_path = path
        for item_path, item in self._item_by_path.items():
            if item_path == path:
                item.setPen(QPen(QColor("#b54708"), 3))
            else:
                item.setPen(QPen(QColor("#344054"), 1.5))

    def _draw_block(self, node: StructureNode, rect: QRectF) -> None:
        if node.node_kind == "system":
            fill = QColor("#d8e7f5")
            subtitle = "Subsystem"
        else:
            fill = QColor("#f0dcc4")
            subtitle = "FMU Component"

        box = _SelectableRectItem(node.path, node.node_kind, rect, self.pathActivated.emit)
        box.setBrush(QBrush(fill))
        box.setPen(QPen(QColor("#344054"), 1.5))
        box.setCursor(Qt.PointingHandCursor)
        self._scene.addItem(box)
        self._item_by_path[node.path] = box

        title = QGraphicsSimpleTextItem(node.name)
        title.setBrush(QBrush(QColor("#0f172a")))
        title.setPos(rect.x() + 12, rect.y() + 10)
        self._scene.addItem(title)

        subtitle_item = QGraphicsSimpleTextItem(subtitle)
        subtitle_item.setBrush(QBrush(QColor("#475467")))
        subtitle_item.setPos(rect.x() + 12, rect.y() + 34)
        self._scene.addItem(subtitle_item)

        meta = f"{len(node.connectors)} connectors"
        if node.node_kind == "system":
            meta += f", {len(node.children)} children"
        meta_item = QGraphicsSimpleTextItem(meta)
        meta_item.setBrush(QBrush(QColor("#475467")))
        meta_item.setPos(rect.x() + 12, rect.y() + 56)
        self._scene.addItem(meta_item)

    def _draw_system_connector_column(
        self,
        connectors: list[ConnectorSummary],
        x: float,
        top_y: float,
        *,
        align_right: bool,
    ) -> None:
        for index, connector in enumerate(connectors):
            y = top_y + index * 34
            label = f"{connector.name} [{connector.kind}]"
            text = self._scene.addText(label)
            if align_right:
                text.setPos(x - text.boundingRect().width(), y)
            else:
                text.setPos(x, y)

    def _draw_connection(
        self,
        connection: ConnectionSummary,
        *,
        node: StructureNode,
        block_geometries: dict[str, _BlockGeometry],
        system_left_x: float,
        system_right_x: float,
    ) -> None:
        start_point = self._resolve_endpoint_point(
            owner_element=connection.start_element,
            connector_name=connection.start_connector,
            node=node,
            block_geometries=block_geometries,
            system_left_x=system_left_x,
            system_right_x=system_right_x,
            is_source=True,
        )
        end_point = self._resolve_endpoint_point(
            owner_element=connection.end_element,
            connector_name=connection.end_connector,
            node=node,
            block_geometries=block_geometries,
            system_left_x=system_left_x,
            system_right_x=system_right_x,
            is_source=False,
        )

        if start_point is None or end_point is None:
            return

        pen = QPen(QColor("#667085"), 1.5)
        self._scene.addLine(start_point.x(), start_point.y(), end_point.x(), end_point.y(), pen)

    def _resolve_endpoint_point(
        self,
        *,
        owner_element: str | None,
        connector_name: str,
        node: StructureNode,
        block_geometries: dict[str, _BlockGeometry],
        system_left_x: float,
        system_right_x: float,
        is_source: bool,
    ) -> QPointF | None:
        if owner_element is None:
            connector = next((c for c in node.connectors if c.name == connector_name), None)
            if connector is None:
                return None
            y = self._system_connector_y(node, connector_name)
            if connector.kind in {"input", "parameter"}:
                return QPointF(system_left_x + 110, y)
            if connector.kind in {"output", "calculatedParameter"}:
                return QPointF(system_right_x - 8, y)
            return QPointF(system_left_x + 110 if is_source else system_right_x - 8, y)

        child = next((child for child in node.children if child.name == owner_element), None)
        if child is None:
            return None

        geometry = block_geometries.get(child.path)
        if geometry is None:
            return None

        connector_index = next(
            (index for index, connector in enumerate(child.connectors) if connector.name == connector_name),
            0,
        )
        y = geometry.rect.y() + 18 + min(connector_index, 4) * 12
        connector = next((c for c in child.connectors if c.name == connector_name), None)
        if connector is not None and connector.kind in {"input", "parameter"}:
            return QPointF(geometry.rect.left(), y)
        if connector is not None and connector.kind in {"output", "calculatedParameter"}:
            return QPointF(geometry.rect.right(), y)
        if is_source:
            return QPointF(geometry.rect.right(), y)
        return QPointF(geometry.rect.left(), y)

    def _system_connector_y(self, node: StructureNode, connector_name: str) -> float:
        connector = next((c for c in node.connectors if c.name == connector_name), None)
        if connector is None:
            return 140

        if connector.kind in {"input", "parameter"}:
            column = [c.name for c in node.connectors if c.kind in {"input", "parameter"}]
            return 128 + column.index(connector_name) * 34

        if connector.kind in {"output", "calculatedParameter"}:
            column = [c.name for c in node.connectors if c.kind in {"output", "calculatedParameter"}]
            return 128 + column.index(connector_name) * 34

        column = [
            c.name
            for c in node.connectors
            if c.kind not in {"input", "parameter", "output", "calculatedParameter"}
        ]
        return 448 + column.index(connector_name) * 34

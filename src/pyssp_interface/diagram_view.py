from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from pyssp_interface.state.diagram_layout import SystemLayout
from pyssp_interface.state.project_state import ConnectionSummary, ConnectorSummary, StructureNode


@dataclass(slots=True)
class _BlockGeometry:
    path: str
    rect: QRectF


class _SelectableRectItem(QGraphicsRectItem):
    def __init__(self, path: str, node_kind: str, rect: QRectF, on_activate, on_moved):
        super().__init__(rect)
        self.path = path
        self.node_kind = node_kind
        self._on_activate = on_activate
        self._on_moved = on_moved
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges, True)

    def mousePressEvent(self, event):
        self._on_activate(self.path)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._on_moved(self.path, self.sceneBoundingRect().topLeft())
        super().mouseReleaseEvent(event)


class _EndpointItem(QGraphicsEllipseItem):
    def __init__(self, owner_path: str, connector_name: str, rect: QRectF, on_activate):
        super().__init__(rect)
        self.owner_path = owner_path
        self.connector_name = connector_name
        self._on_activate = on_activate
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self._on_activate(self.owner_path, self.connector_name)
        super().mousePressEvent(event)


class _SelectableConnectionItem(QGraphicsLineItem):
    def __init__(self, owner_path: str, key: tuple[str | None, str, str | None, str], on_activate):
        super().__init__()
        self.owner_path = owner_path
        self.key = key
        self._on_activate = on_activate
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self._on_activate(self.owner_path, self.key)
        super().mousePressEvent(event)


class DiagramView(QGraphicsView):
    pathActivated = Signal(str)
    blockMoved = Signal(str, str, float, float)
    endpointActivated = Signal(str, str)
    connectionActivated = Signal(str, object)

    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setBackgroundBrush(QBrush(QColor("#f7f6f1")))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self._item_by_path: dict[str, _SelectableRectItem] = {}
        self._endpoint_items: dict[tuple[str, str], _EndpointItem] = {}
        self._connection_items: dict[tuple[str, tuple[str | None, str, str | None, str]], _SelectableConnectionItem] = {}
        self._highlighted_path: str | None = None
        self._selected_endpoint: tuple[str, str] | None = None
        self._selected_connection: tuple[str, tuple[str | None, str, str | None, str]] | None = None
        self._current_system_path: str | None = None

    def render_system(
        self,
        node: StructureNode | None,
        *,
        layout: SystemLayout | None = None,
    ) -> None:
        self._scene.clear()
        self._item_by_path.clear()
        self._endpoint_items.clear()
        self._connection_items.clear()
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
        top_y = 120

        block_geometries: dict[str, _BlockGeometry] = {}

        self._draw_system_connector_column(left_connectors, system_left_x, top_y, align_right=False)
        self._draw_system_connector_column(right_connectors, system_right_x, top_y, align_right=True)
        self._draw_system_connector_column(other_connectors, 40, top_y + 320, align_right=False)

        for child in node.children:
            block_layout = layout.blocks.get(child.path) if layout is not None else None
            rect = QRectF(
                block_layout.x if block_layout is not None else 280.0,
                block_layout.y if block_layout is not None else top_y,
                block_layout.width if block_layout is not None else 240.0,
                block_layout.height if block_layout is not None else 84.0,
            )
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
        self.set_selected_endpoint(self._selected_endpoint)
        self.set_selected_connection(self._selected_connection)

    def set_highlighted_path(self, path: str | None) -> None:
        self._highlighted_path = path
        for item_path, item in self._item_by_path.items():
            if item_path == path:
                item.setPen(QPen(QColor("#b54708"), 3))
            else:
                item.setPen(QPen(QColor("#344054"), 1.5))

    def set_selected_endpoint(self, endpoint: tuple[str, str] | None) -> None:
        self._selected_endpoint = endpoint
        for key, item in self._endpoint_items.items():
            if key == endpoint:
                item.setBrush(QBrush(QColor("#f79009")))
                item.setPen(QPen(QColor("#b54708"), 2))
            else:
                item.setBrush(QBrush(QColor("#98a2b3")))
                item.setPen(QPen(QColor("#344054"), 1))

    def set_selected_connection(
        self,
        connection: tuple[str, tuple[str | None, str, str | None, str]] | None,
    ) -> None:
        self._selected_connection = connection
        for key, item in self._connection_items.items():
            if key == connection:
                item.setPen(QPen(QColor("#b54708"), 3))
            else:
                item.setPen(QPen(QColor("#667085"), 3))

    @property
    def current_system_path(self) -> str | None:
        return self._current_system_path

    def _draw_block(self, node: StructureNode, rect: QRectF) -> None:
        if node.node_kind == "system":
            fill = QColor("#d8e7f5")
            subtitle = "Subsystem"
        else:
            fill = QColor("#f0dcc4")
            subtitle = "FMU Component"

        box = _SelectableRectItem(
            node.path,
            node.node_kind,
            rect,
            self.pathActivated.emit,
            self._emit_block_moved,
        )
        box.setBrush(QBrush(fill))
        box.setPen(QPen(QColor("#344054"), 1.5))
        box.setCursor(Qt.PointingHandCursor)
        self._scene.addItem(box)
        self._item_by_path[node.path] = box

        title = QGraphicsSimpleTextItem(node.name, box)
        title.setBrush(QBrush(QColor("#0f172a")))
        title.setPos(12, 10)

        subtitle_item = QGraphicsSimpleTextItem(subtitle, box)
        subtitle_item.setBrush(QBrush(QColor("#475467")))
        subtitle_item.setPos(12, 34)

        meta = f"{len(node.connectors)} connectors"
        if node.node_kind == "system":
            meta += f", {len(node.children)} children"
        meta_item = QGraphicsSimpleTextItem(meta, box)
        meta_item.setBrush(QBrush(QColor("#475467")))
        meta_item.setPos(12, 56)

        self._draw_block_connectors(node, rect)

    def _emit_block_moved(self, path: str, position: QPointF) -> None:
        if self._current_system_path is None:
            return
        self.blockMoved.emit(self._current_system_path, path, position.x(), position.y())

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
            endpoint_x = x - 16 if align_right else x - 6
            self._add_endpoint_item(
                connector.owner_path,
                connector.name,
                QRectF(endpoint_x, y + 3, 10, 10),
            )
            label = f"{connector.name} [{connector.kind}]"
            text = self._scene.addText(label)
            if align_right:
                text.setPos(x - text.boundingRect().width(), y)
            else:
                text.setPos(x, y)

    def _draw_block_connectors(self, node: StructureNode, rect: QRectF) -> None:
        left_connectors = [c for c in node.connectors if c.kind in {"input", "parameter"}]
        right_connectors = [c for c in node.connectors if c.kind in {"output", "calculatedParameter"}]
        other_connectors = [
            c
            for c in node.connectors
            if c.kind not in {"input", "parameter", "output", "calculatedParameter"}
        ]

        self._draw_block_connector_column(
            node.path,
            left_connectors,
            rect.left() - 6,
            rect.top() + 12,
            align_right=True,
        )
        self._draw_block_connector_column(
            node.path,
            right_connectors,
            rect.right() - 4,
            rect.top() + 12,
            align_right=False,
        )
        self._draw_block_connector_column(
            node.path,
            other_connectors,
            rect.left() + 12,
            rect.bottom() - 18,
            align_right=False,
        )

    def _draw_block_connector_column(
        self,
        owner_path: str,
        connectors: list[ConnectorSummary],
        x: float,
        top_y: float,
        *,
        align_right: bool,
    ) -> None:
        for index, connector in enumerate(connectors[:6]):
            y = top_y + index * 12
            self._add_endpoint_item(owner_path, connector.name, QRectF(x, y, 8, 8))
            label = QGraphicsSimpleTextItem(connector.name)
            label.setBrush(QBrush(QColor("#475467")))
            if align_right:
                label.setPos(x - label.boundingRect().width() - 4, y - 4)
            else:
                label.setPos(x + 12, y - 4)
            self._scene.addItem(label)

    def _add_endpoint_item(self, owner_path: str, connector_name: str, rect: QRectF) -> None:
        item = _EndpointItem(owner_path, connector_name, rect, self.endpointActivated.emit)
        item.setBrush(QBrush(QColor("#98a2b3")))
        item.setPen(QPen(QColor("#344054"), 1))
        self._scene.addItem(item)
        self._endpoint_items[(owner_path, connector_name)] = item

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

        key = (
            connection.start_element,
            connection.start_connector,
            connection.end_element,
            connection.end_connector,
        )
        item = _SelectableConnectionItem(
            connection.owner_path,
            key,
            self.connectionActivated.emit,
        )
        item.setLine(start_point.x(), start_point.y(), end_point.x(), end_point.y())
        item.setPen(QPen(QColor("#667085"), 3))
        self._scene.addItem(item)
        self._connection_items[(connection.owner_path, key)] = item

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
            key = (node.path, connector_name)
            endpoint_item = self._endpoint_items.get(key)
            if endpoint_item is not None:
                center = endpoint_item.sceneBoundingRect().center()
                return center
            if connector.kind in {"input", "parameter"}:
                y = self._system_connector_y(node, connector_name)
                return QPointF(system_left_x + 110, y)
            if connector.kind in {"output", "calculatedParameter"}:
                y = self._system_connector_y(node, connector_name)
                return QPointF(system_right_x - 8, y)
            y = self._system_connector_y(node, connector_name)
            return QPointF(system_left_x + 110 if is_source else system_right_x - 8, y)

        child = next((child for child in node.children if child.name == owner_element), None)
        if child is None:
            return None

        geometry = block_geometries.get(child.path)
        if geometry is None:
            return None

        endpoint_item = self._endpoint_items.get((child.path, connector_name))
        if endpoint_item is not None:
            return endpoint_item.sceneBoundingRect().center()

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

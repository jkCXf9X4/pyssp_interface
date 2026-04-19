from __future__ import annotations

from dataclasses import dataclass

from pyssp_interface.state.diagram_layout import DiagramLayoutStore, SystemLayout
from pyssp_interface.state.project_state import (
    ConnectionSummary,
    DiagramLayoutData,
    ProjectSnapshot,
    StructureNode,
)

ConnectionKey = tuple[str | None, str, str | None, str]
DiagramEndpoint = tuple[str, str]
DiagramSelection = tuple[str, ConnectionKey]


@dataclass(slots=True)
class DiagramRenderState:
    layout: SystemLayout | None
    highlighted_path: str | None
    selected_endpoint: DiagramEndpoint | None
    selected_connection: DiagramSelection | None


@dataclass(slots=True)
class EndpointActivationResult:
    status: str
    snapshot: ProjectSnapshot | None = None
    message: str | None = None


class DiagramController:
    def __init__(self, layout_store: DiagramLayoutStore | None = None):
        self._layout_store = layout_store or DiagramLayoutStore()
        self.pending_endpoint: DiagramEndpoint | None = None
        self.selected_connection: DiagramSelection | None = None

    def reset(self, layouts: DiagramLayoutData | None = None) -> None:
        self.pending_endpoint = None
        self.selected_connection = None
        self._layout_store.load(layouts or {})

    def activate_endpoint(
        self,
        *,
        owner_path: str,
        connector_name: str,
        system_path: str | None,
        create_connection,
    ) -> EndpointActivationResult:
        endpoint = (owner_path, connector_name)
        self.selected_connection = None

        if system_path is None:
            return EndpointActivationResult(status="ignored")

        if self.pending_endpoint == endpoint:
            self.pending_endpoint = None
            return EndpointActivationResult(
                status="cleared",
                message="Cleared pending diagram endpoint",
            )

        if self.pending_endpoint is None:
            self.pending_endpoint = endpoint
            return EndpointActivationResult(
                status="pending",
                message=f"Selected start endpoint {owner_path}::{connector_name}. Select an end endpoint.",
            )

        start_owner_path, start_connector = self.pending_endpoint
        snapshot = create_connection(
            start_owner_path=start_owner_path,
            start_connector=start_connector,
            end_owner_path=owner_path,
            end_connector=connector_name,
            system_path=system_path,
        )
        self.pending_endpoint = None
        return EndpointActivationResult(
            status="created",
            snapshot=snapshot,
            message=(
                f"Added connection {start_owner_path}::{start_connector} -> "
                f"{owner_path}::{connector_name}"
            ),
        )

    def activate_connection(
        self,
        *,
        owner_path: str,
        key: ConnectionKey,
        connection: ConnectionSummary | None,
    ) -> str | None:
        if connection is None:
            return None
        self.pending_endpoint = None
        self.selected_connection = (owner_path, key)
        return (
            f"Selected connection {owner_path}: "
            f"{connection.start_connector} -> {connection.end_connector}"
        )

    def update_block_position(
        self,
        *,
        system_path: str,
        block_path: str,
        x: float,
        y: float,
    ) -> None:
        self._layout_store.update_block_position(system_path, block_path, x=x, y=y)

    def render_state(
        self,
        node: StructureNode | None,
        *,
        highlighted_path: str | None,
    ) -> DiagramRenderState:
        if self.pending_endpoint is not None and not self._endpoint_in_scope(node, self.pending_endpoint):
            self.pending_endpoint = None
        if self.selected_connection is not None and not self._connection_in_scope(node, self.selected_connection):
            self.selected_connection = None
        return DiagramRenderState(
            layout=self._layout_store.layout_for(node),
            highlighted_path=highlighted_path,
            selected_endpoint=self.pending_endpoint,
            selected_connection=self.selected_connection,
        )

    @staticmethod
    def _endpoint_in_scope(
        node: StructureNode | None,
        endpoint: DiagramEndpoint,
    ) -> bool:
        if node is None or node.node_kind != "system":
            return False
        owner_path, _ = endpoint
        if owner_path == node.path:
            return True
        return any(child.path == owner_path for child in node.children)

    @staticmethod
    def _connection_in_scope(
        node: StructureNode | None,
        connection: DiagramSelection,
    ) -> bool:
        if node is None or node.node_kind != "system":
            return False
        owner_path, _ = connection
        return owner_path == node.path

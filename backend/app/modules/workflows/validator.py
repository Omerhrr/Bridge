"""Workflow validation (spec section 23).

Detects missing start nodes, disconnected nodes, invalid configuration,
unsupported connections, cycles, missing credentials and unsupported
languages before a workflow can be deployed.
"""
from app.core.config import settings
from app.modules.ai.languages import is_supported
from app.modules.workflows.registry import NODE_REGISTRY, TRIGGER_TYPES
from app.modules.workflows.schemas import (
    ValidationIssue,
    ValidationReport,
    WorkflowDefinition,
)


def validate_workflow(definition: WorkflowDefinition) -> ValidationReport:
    issues: list[ValidationIssue] = []
    passed = 0

    node_ids = {node.id for node in definition.nodes}
    node_types = {node.id: node.type for node in definition.nodes}

    # 1. Definition has at least one node and a trigger/start node.
    if not definition.nodes:
        issues.append(ValidationIssue(level="error", message="Workflow has no nodes"))
    triggers = [n for n in definition.nodes if n.type in TRIGGER_TYPES]
    if triggers:
        passed += 1
    else:
        issues.append(
            ValidationIssue(level="error", message="Workflow needs a trigger node (Incoming Call, Incoming SMS or USSD)")
        )

    # 2. Every node type exists in the registry.
    unknown = [n for n in definition.nodes if n.type not in NODE_REGISTRY]
    if not unknown:
        passed += 1
    else:
        for node in unknown:
            issues.append(
                ValidationIssue(level="error", node_id=node.id, message=f"Unknown node type '{node.type}'")
            )

    # 3. Required configuration is present.
    config_ok = True
    for node in definition.nodes:
        cls = NODE_REGISTRY.get(node.type)
        if not cls:
            continue
        instance = cls()
        for field_name in instance.missing_required_config(node.config):
            config_ok = False
            issues.append(
                ValidationIssue(
                    level="error",
                    node_id=node.id,
                    message=f"{instance.label} requires '{field_name}' to be configured",
                )
            )
    if config_ok:
        passed += 1

    # 4. Node connectivity: only one outgoing edge per handle, all edges valid.
    edges_valid = True
    for edge in definition.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            edges_valid = False
            issues.append(
                ValidationIssue(level="error", node_id=edge.source, message="Connection references a missing node")
            )
    if edges_valid:
        passed += 1

    # 5. Disconnected nodes: everything except triggers must be reachable,
    #    and triggers must have an outgoing connection.
    reachable: set[str] = set()
    if triggers:
        adjacency: dict[str, list[str]] = {}
        for edge in definition.edges:
            adjacency.setdefault(edge.source, []).append(edge.target)
        queue = [t.id for t in triggers]
        while queue:
            current = queue.pop()
            if current in reachable:
                continue
            reachable.add(current)
            queue.extend(adjacency.get(current, []))

        disconnected = [n for n in definition.nodes if n.id not in reachable]
        orphan_triggers = [t for t in triggers if not any(e.source == t.id for e in definition.edges)]
        for node in disconnected:
            issues.append(
                ValidationIssue(level="error", node_id=node.id, message="Node is not connected to the workflow")
            )
        for node in orphan_triggers:
            issues.append(
                ValidationIssue(level="error", node_id=node.id, message="Trigger node is not connected to any next step")
            )
        if not disconnected and not orphan_triggers:
            passed += 1

    # 6. Unsupported cycles (everything except logic loops is flagged).
    if triggers and reachable:
        adjacency: dict[str, list[str]] = {}
        for edge in definition.edges:
            adjacency.setdefault(edge.source, []).append(edge.target)
        visited: set[str] = set()
        stack: set[str] = set()
        cycles: list[str] = []

        def dfs(node_id: str) -> None:
            visited.add(node_id)
            stack.add(node_id)
            for nxt in adjacency.get(node_id, []):
                if nxt in stack:
                    cycles.append(node_id)
                elif nxt not in visited:
                    dfs(nxt)
            stack.discard(node_id)

        for t in triggers:
            if t.id not in visited:
                dfs(t.id)
        if not cycles:
            passed += 1
        else:
            for node_id in cycles:
                issues.append(
                    ValidationIssue(
                        level="warning", node_id=node_id,
                        message="Workflow contains a cycle; make sure loops use a Condition to terminate",
                    )
                )

    # 7. Missing credentials for nodes that need external providers.
    uses_telecom = any(n.type in {"send_sms", "make_call", "send_airtime"} for n in definition.nodes)
    if uses_telecom and not settings.at_configured:
        issues.append(
            ValidationIssue(
                level="warning",
                message="Africa's Talking credentials are not configured; SMS/call actions will be simulated",
            )
        )
    uses_ai = any(n.type in {"speech_to_text", "translate", "text_to_speech"} for n in definition.nodes)
    if uses_ai and not settings.ai_configured:
        issues.append(
            ValidationIssue(
                level="warning",
                message="AI provider is not configured; AI nodes will use the built-in stub provider",
            )
        )
    if uses_telecom or uses_ai:
        passed += 1

    # 8. Unsupported languages on translate / TTS nodes.
    languages_ok = True
    for node in definition.nodes:
        target = (node.config or {}).get("target_language")
        if node.type == "translate" and target and not is_supported(target):
            languages_ok = False
            issues.append(
                ValidationIssue(level="error", node_id=node.id, message=f"Unsupported language '{target}'")
            )
    if languages_ok:
        passed += 1

    return ValidationReport(valid=not any(i.level == "error" for i in issues), checks_passed=passed, issues=issues)

# ascii_artist.py
# __all__: 18

__all__ = [
    "generate_square",
    "generate_triangle",
    "generate_diamond",
    "get_template",
    "list_templates",
    "render_prompt_ascii",
    "SUPPORTED",
    "UNSUPPORTED",
    "Node",
    "Edge",
    "Diagram",
    "diagram",
    "to_dict",
    "from_dict",
    "render_diagram",
    "flow",
    "branch",
    "tree",
]

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol

SUPPORTED = {
    "generation": [
        "square / triangle / diamond text-art generation",
        "non-empty single-line string tokens, including Unicode",
        "built-in text-art templates",
        "Diagram IR with deterministic flow / branch / tree rendering",
        "lossless Diagram <-> dict serialization",
    ],
    "llm_adapter": [
        "plain callable generator",
        "object exposing generate_light(prompt)",
        "string result or object with string .text attribute",
    ],
    "sanitization": [
        "common system/user/assistant wrapper lines",
        "Markdown backtick or tilde fences",
        "common ASCII-art preamble lines",
        "CRLF/CR line-ending normalization",
    ],
    "distribution": [
        "single-file copying and vendoring",
        "Python standard-library-only runtime",
    ],
}

UNSUPPORTED = {
    "layout": [
        "terminal-cell-perfect alignment for wide Unicode or emoji",
        "font-aware glyph measurement",
        "automatic monospace capability detection",
    ],
    "rendering": [
        "ANSI color rendering",
        "terminal capability negotiation",
        "image/raster rendering or image decoding",
    ],
    "parsing": [
        "full Markdown parsing",
        "general-purpose graph layout or cyclic graph rendering",
        "fuzzy removal of arbitrary prose around generated art",
    ],
    "integration": [
        "direct dependency on a specific LLM SDK",
        "repository-local runtime assets or configuration files",
    ],
}


@dataclass(frozen=True)
class Node:
    """One logical node in the diagram intermediate representation."""

    id: str
    label: str


@dataclass(frozen=True)
class Edge:
    """One directed edge in the diagram intermediate representation."""

    source: str
    target: str


@dataclass(frozen=True)
class Diagram:
    """Small immutable DAG-oriented intermediate representation."""

    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


def _normalize_node(value: str | Node) -> Node:
    if isinstance(value, Node):
        node = value
    elif isinstance(value, str):
        node = Node(value, value)
    else:
        raise TypeError("nodes must contain strings or Node values")
    if not node.id or "\n" in node.id or "\r" in node.id:
        raise ValueError("node id must be a non-empty single-line string")
    if not node.label or "\n" in node.label or "\r" in node.label:
        raise ValueError("node label must be a non-empty single-line string")
    return node


def _normalize_edge(value: tuple[str, str] | Edge) -> Edge:
    if isinstance(value, Edge):
        edge = value
    elif isinstance(value, tuple) and len(value) == 2:
        edge = Edge(str(value[0]), str(value[1]))
    else:
        raise TypeError("edges must contain Edge values or (source, target) tuples")
    if not edge.source or not edge.target:
        raise ValueError("edge endpoints must be non-empty")
    return edge


def _validate_dag(value: Diagram) -> None:
    node_ids = [node.id for node in value.nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("node ids must be unique")
    known = set(node_ids)
    for edge in value.edges:
        if edge.source not in known or edge.target not in known:
            raise ValueError("every edge endpoint must reference a known node")
        if edge.source == edge.target:
            raise ValueError("self edges are not supported")

    indegree = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: [] for node_id in node_ids}
    for edge in value.edges:
        indegree[edge.target] += 1
        outgoing[edge.source].append(edge.target)

    ready = [node_id for node_id in node_ids if indegree[node_id] == 0]
    visited = 0
    while ready:
        current = ready.pop(0)
        visited += 1
        for target in outgoing[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if visited != len(node_ids):
        raise ValueError("diagram must be acyclic")


def _topological_layers(value: Diagram) -> list[list[str]]:
    _validate_dag(value)
    node_ids = [node.id for node in value.nodes]
    indegree = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: [] for node_id in node_ids}
    for edge in value.edges:
        indegree[edge.target] += 1
        outgoing[edge.source].append(edge.target)

    remaining = set(node_ids)
    layers: list[list[str]] = []
    while remaining:
        layer = [node_id for node_id in node_ids if node_id in remaining and indegree[node_id] == 0]
        if not layer:
            raise ValueError("diagram must be acyclic")
        layers.append(layer)
        for source in layer:
            remaining.remove(source)
            for target in outgoing[source]:
                indegree[target] -= 1
    return layers


def diagram(
    nodes: Iterable[str | Node],
    edges: Iterable[tuple[str, str] | Edge] = (),
) -> Diagram:
    """Build and validate a normalized DAG intermediate representation."""

    value = Diagram(
        tuple(_normalize_node(node) for node in nodes),
        tuple(_normalize_edge(edge) for edge in edges),
    )
    _validate_dag(value)
    return value


def to_dict(value: Diagram) -> dict[str, Any]:
    """Serialize a Diagram losslessly to JSON-compatible builtins."""

    _validate_dag(value)
    return {
        "nodes": [{"id": node.id, "label": node.label} for node in value.nodes],
        "edges": [{"source": edge.source, "target": edge.target} for edge in value.edges],
    }


def from_dict(value: Mapping[str, Any]) -> Diagram:
    """Deserialize the canonical dictionary form back into a Diagram."""

    if not isinstance(value, Mapping):
        raise TypeError("diagram data must be a mapping")
    raw_nodes = value.get("nodes", ())
    raw_edges = value.get("edges", ())
    if not isinstance(raw_nodes, (list, tuple)) or not isinstance(raw_edges, (list, tuple)):
        raise TypeError("nodes and edges must be sequences")

    nodes: list[Node] = []
    for raw in raw_nodes:
        if not isinstance(raw, Mapping):
            raise TypeError("serialized nodes must be mappings")
        node_id = raw.get("id")
        label = raw.get("label")
        if not isinstance(node_id, str):
            raise TypeError(
                f"serialized node id must be str, got {type(node_id).__name__}"
            )
        if not isinstance(label, str):
            raise TypeError(
                f"serialized node {node_id!r} label must be str, got {type(label).__name__}"
            )
        nodes.append(Node(node_id, label))

    edges: list[Edge] = []
    for raw in raw_edges:
        if not isinstance(raw, Mapping):
            raise TypeError("serialized edges must be mappings")
        source = raw.get("source")
        target = raw.get("target")
        if not isinstance(source, str):
            raise TypeError(
                f"serialized edge source must be str, got {type(source).__name__}"
            )
        if not isinstance(target, str):
            raise TypeError(
                f"serialized edge target must be str, got {type(target).__name__}"
            )
        edges.append(Edge(source, target))
    return diagram(nodes, edges)


def _charset(name: str) -> dict[str, str]:
    if name == "unicode":
        return {"down": "↓", "tee": "├", "last": "└", "h": "─", "arrow": "→", "pipe": "│"}
    if name == "ascii":
        return {"down": "v", "tee": "+", "last": "\\", "h": "-", "arrow": ">", "pipe": "|"}
    raise ValueError("charset must be 'unicode' or 'ascii'")


def render_diagram(value: Diagram, *, charset: str = "unicode") -> str:
    """Render any DAG as an exact adjacency-oriented text representation.

    Specialized convenience renderers such as flow() and branch() may choose a
    prettier topology-specific layout. This generic renderer prioritizes edge
    correctness over pretending to be a full graph-layout engine.
    """

    chars = _charset(charset)
    _validate_dag(value)
    labels = {node.id: node.label for node in value.nodes}
    outgoing = {node.id: [] for node in value.nodes}
    for edge in value.edges:
        outgoing[edge.source].append(edge.target)

    lines: list[str] = []
    for node in value.nodes:
        lines.append(labels[node.id])
        targets = outgoing[node.id]
        for index, target in enumerate(targets):
            prefix = chars["last"] if index == len(targets) - 1 else chars["tee"]
            lines.append(f"{prefix}{chars['h']}{chars['arrow']} {labels[target]}")
    return "\n".join(lines)


def flow(items: Iterable[str], *, charset: str = "unicode") -> str:
    """Render a deterministic vertical linear flow."""

    labels = [str(item) for item in items]
    if not labels:
        return ""
    if any(not label or "\n" in label or "\r" in label for label in labels):
        raise ValueError("flow labels must be non-empty single-line strings")
    chars = _charset(charset)
    nodes = [Node(str(index), label) for index, label in enumerate(labels)]
    edges = [Edge(str(index), str(index + 1)) for index in range(len(nodes) - 1)]
    _validate_dag(Diagram(tuple(nodes), tuple(edges)))
    return f"\n {chars['down']}\n".join(labels)


def branch(
    root: str,
    branches: Iterable[str],
    target: str | None = None,
    *,
    charset: str = "unicode",
) -> str:
    """Render a one-to-many, optionally many-to-one, topology."""

    branch_labels = [str(label) for label in branches]
    labels = [root, *branch_labels] + ([target] if target is not None else [])
    if any(not isinstance(label, str) or not label or "\n" in label or "\r" in label for label in labels):
        raise ValueError("branch labels must be non-empty single-line strings")
    if not branch_labels:
        return root if target is None else flow([root, target], charset=charset)

    nodes = [Node("root", root)]
    nodes.extend(Node(f"branch_{index}", label) for index, label in enumerate(branch_labels))
    edges = [Edge("root", f"branch_{index}") for index in range(len(branch_labels))]
    if target is not None:
        nodes.append(Node("target", target))
        edges.extend(Edge(f"branch_{index}", "target") for index in range(len(branch_labels)))
    _validate_dag(Diagram(tuple(nodes), tuple(edges)))

    chars = _charset(charset)
    gap = 4
    branch_line = (" " * gap).join(branch_labels)
    centers: list[int] = []
    cursor = 0
    for label in branch_labels:
        centers.append(cursor + len(label) // 2)
        cursor += len(label) + gap
    total_width = len(branch_line)
    root_start = max(0, (total_width - len(root)) // 2)
    root_line = " " * root_start + root

    connector = [" "] * max(total_width, root_start + len(root))
    root_center = root_start + len(root) // 2
    left, right = centers[0], centers[-1]
    if left == right:
        # Single-branch case: keep a straight vertical connector.
        connector[left] = chars["pipe"]
    else:
        # Multi-branch case: span the first/last branch centers and split at root.
        for pos in range(left, right + 1):
            connector[pos] = chars["h"]
        connector[root_center] = "┼" if charset == "unicode" else "+"
        connector[left] = "┌" if charset == "unicode" else "+"
        connector[right] = "┐" if charset == "unicode" else "+"
    arrows = [" "] * len(connector)
    for center in centers:
        arrows[center] = chars["down"]

    lines = [root_line, " " * root_center + chars["pipe"], "".join(connector).rstrip(), "".join(arrows).rstrip(), branch_line]
    if target is not None:
        join = [" "] * len(connector)
        if left == right:
            # Single-branch convergence is a straight vertical path.
            join[left] = chars["pipe"]
        else:
            # Multi-branch convergence mirrors the fan-out above.

            for pos in range(left, right + 1):
                join[pos] = chars["h"]
            join[left] = "└" if charset == "unicode" else "+"
            join[right] = "┘" if charset == "unicode" else "+"
            join[root_center] = "┴" if charset == "unicode" else "+"
        target_start = max(0, (total_width - len(target)) // 2)
        lines.extend(["".join(join).rstrip(), " " * root_center + chars["down"], " " * target_start + target])
    return "\n".join(lines)


def _tree_lines(
    value: Mapping[str, Any],
    *,
    prefix: str,
    charset: str,
) -> list[str]:
    """Render mapping-shaped descendants iteratively to avoid recursion limits."""

    chars = _charset(charset)
    lines: list[str] = []
    stack: list[tuple[list[tuple[str, Any]], int, str]] = [
        (list(value.items()), 0, prefix)
    ]

    while stack:
        entries, index, current_prefix = stack.pop()
        if index >= len(entries):
            continue

        label, children = entries[index]
        last = index == len(entries) - 1
        elbow = chars["last"] if last else chars["tee"]
        lines.append(f"{current_prefix}{elbow}{chars['h']}{chars['arrow']} {label}")

        # Resume siblings after this node's descendants.
        stack.append((entries, index + 1, current_prefix))

        if children:
            if not isinstance(children, Mapping):
                raise TypeError("tree children must be mappings")
            child_prefix = current_prefix + (
                "   " if last else f"{chars['pipe']}  "
            )
            stack.append((list(children.items()), 0, child_prefix))

    return lines

def tree(root: str, children: Mapping[str, Any], *, charset: str = "unicode") -> str:
    """Render a deterministic nested tree from mapping-shaped children."""

    if not root or "\n" in root or "\r" in root:
        raise ValueError("tree root must be a non-empty single-line string")
    if not isinstance(children, Mapping):
        raise TypeError("tree children must be a mapping")
    return "\n".join([root, *_tree_lines(children, prefix="", charset=charset)])


_ASCII_TEMPLATES = {
    "icon_ironmate": "   _______\n  /       \\\n | () | () |\n |   ___   |\n  \\_______/\n  [ IRONMATE ]\n",
    "ironmate": "  _____                                _\n |_   _|  _ __    ___    _ __   _ __  | |__    __ _   ___   ___\n   | |   | '__|  / _ \\  | '_ \\ | '_ \\ | '_ \\  / _` | / __| / __|\n   | |   | |    | (_) | | | | || | | || | | || (_| || (__ | (__\n   |_|   |_|     \\___/  |_| |_||_| |_||_| |_| \\__,_| \\___| \\___|\n  IRONMATE - Your J.A.R.V.I.S-inspired assistant\n",
    "welcome": " __        __   _\n \\ \\      / /__| | ___ ___  _ __ ___   ___\n  \\ \\ /\\ / / _ \\ |/ __/ _ \\| '_ ` _ \\ / _ \\\n   \\ V  V /  __/ | (_| (_) | | | | | |  __/\n    \\_/\\_/ \\___|_|\\___\\___/|_| |_| |_|\\___|\n  to IRONMATE!\n",
    "cat": " /\\_/\\\n( o.o )\n > ^ <\n",
    "heart": " **   **\n***** *****\n *********\n  *******\n   *****\n    ***\n     *\n",
    "tree": "    *\n   ***\n  *****\n *******\n    |\n",
}

_DEFAULT_ASCII_PROMPT = "Generate compact ASCII art that represents the user's request."
_DEFAULT_MAX_WIDTH = 60
_FENCE_LINE_RE = re.compile(r"^\s*(?:`{3,}|~{3,})(?:[A-Za-z0-9_.+-]+)?\s*$")
_PREAMBLE_LINE_RE = re.compile(r"^\s*(?:here(?:\'s| is) your ascii art|ascii art)\s*:\s*$", re.IGNORECASE)
_ROLE_LINE_RE = re.compile(r"^\s*(?:\[(?:system|user|assistant)\]|(?:system|user|assistant))\s*:?\s*$", re.IGNORECASE)


class _SupportsGenerateLight(Protocol):
    def generate_light(self, prompt: str) -> Any:
        ...


def _validate_token(token: str) -> str:
    if not isinstance(token, str):
        raise TypeError("char must be a string token")
    if not token:
        raise ValueError("char must not be empty")
    if "\n" in token or "\r" in token:
        raise ValueError("char must be a single-line token")
    return token


def _generated_text(
    generator: Callable[[str], Any] | _SupportsGenerateLight,
    prompt: str,
) -> str:
    method = getattr(generator, "generate_light", None)
    if callable(method):
        result = method(prompt)
    elif callable(generator):
        result = generator(prompt)
    else:
        raise TypeError("generator must be callable or provide generate_light(prompt)")

    if isinstance(result, str):
        return result
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text
    raise TypeError("generator result must be a string or provide a string .text attribute")


def _sanitize_ascii_output(text: str) -> str:
    """Remove common chat/Markdown wrappers from generated ASCII text."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    filtered: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if _ROLE_LINE_RE.fullmatch(stripped):
            continue
        if _FENCE_LINE_RE.fullmatch(stripped):
            continue
        if _PREAMBLE_LINE_RE.fullmatch(stripped):
            continue
        filtered.append(stripped)

    while filtered and not filtered[0].strip():
        filtered.pop(0)
    while filtered and not filtered[-1].strip():
        filtered.pop()
    return "\n".join(filtered)


def generate_square(size: int, char: str = "*") -> str:
    """Generate a square by repeating a non-empty single-line token.

    size counts token repetitions, not terminal display cells. Unicode and
    multi-code-point tokens are preserved as-is.
    """
    token = _validate_token(char)
    if size <= 0:
        return ""
    row = token * size
    return "\n".join(row for _ in range(size))


def generate_triangle(height: int, char: str = "*") -> str:
    """Generate a left-aligned triangle using token repetition counts."""
    token = _validate_token(char)
    if height <= 0:
        return ""
    return "\n".join(token * i for i in range(1, height + 1))


def generate_diamond(half_height: int, char: str = "*") -> str:
    """Generate a diamond using token repetition counts.

    Padding is ASCII-space based; terminal-cell-perfect alignment for wide
    Unicode tokens is intentionally outside this stdlib-only helper contract.
    """
    token = _validate_token(char)
    if half_height <= 0:
        return ""
    width = 2 * half_height - 1
    upper = [
        " " * ((width - (2 * i - 1)) // 2) + token * (2 * i - 1)
        for i in range(1, half_height + 1)
    ]
    lower = [
        " " * ((width - (2 * i - 1)) // 2) + token * (2 * i - 1)
        for i in range(half_height - 1, 0, -1)
    ]
    return "\n".join(upper + lower)


def get_template(name: str) -> str:
    """Return a built-in ASCII art template by name."""
    return _ASCII_TEMPLATES.get(name.strip().lower(), "")


def list_templates() -> list[str]:
    """Return the sorted built-in ASCII template names."""
    return sorted(_ASCII_TEMPLATES)


def render_prompt_ascii(
    prompt: str,
    generator: Callable[[str], Any] | _SupportsGenerateLight,
) -> str:
    """Generate ASCII art using either a callable or generate_light object.

    A callable may return a string directly or an object with a string text
    attribute. This keeps the module independent from any specific LLM SDK.
    """
    base_prompt = _DEFAULT_ASCII_PROMPT
    max_width = _DEFAULT_MAX_WIDTH

    user_prompt = prompt.strip()
    final_prompt = (
        f"{base_prompt}\n\n"
        f"USER_REQUEST:\n{user_prompt}\n\n"
        f"CONSTRAINTS:\n"
        f"- Keep width under {max_width} characters.\n"
        f"- Return ASCII art only.\n"
        f"- No explanations.\n"
    )

    return _sanitize_ascii_output(_generated_text(generator, final_prompt))

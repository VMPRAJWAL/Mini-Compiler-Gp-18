"""Interactive HTML visualizer for the mini-compiler pipeline.

The module intentionally uses only the Python standard library, so it can be
run directly from a checkout:

    python pipeline_visualizer.py example.mc --open

It also exposes ``render_pipeline(source)`` for notebooks or other tools that
want the generated HTML without writing a file.
"""

from __future__ import annotations

import argparse
import html
import tempfile
import webbrowser
from pathlib import Path
from typing import Any

from ast_nodes import Assign, BinOp, If, Num, Print, Program, Var, While
from code_generator import CodeGenerationError, generate
from lexer import lexer
from parser import parse


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _tokens_table(tokens: list[tuple[str, str]]) -> str:
    if not tokens:
        return "<p class='muted'>No tokens produced.</p>"

    rows = "".join(
        f"<tr><td>{index}</td><td><code>{_escape(token_type)}</code></td>"
        f"<td><code>{_escape(text or '∅')}</code></td></tr>"
        for index, (token_type, text) in enumerate(tokens)
    )
    return (
        "<table><thead><tr><th>#</th><th>Type</th><th>Text</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _node_label(node: Any) -> str:
    if isinstance(node, Program):
        return "Program"
    if isinstance(node, Assign):
        return f"Assign: {node.name}"
    if isinstance(node, Print):
        return "Print"
    if isinstance(node, If):
        return "If"
    if isinstance(node, While):
        return "While"
    if isinstance(node, BinOp):
        return f"BinOp: {node.op}"
    if isinstance(node, Num):
        return f"Num: {node.value}"
    if isinstance(node, Var):
        return f"Var: {node.name}"
    return type(node).__name__


def _ast_edges(
    node: Any,
    edges: list[tuple[str, str]] | None = None,
    nodes: list[tuple[str, str]] | None = None,
):
    """Return node labels and parent-child edges for an AST."""
    if edges is None:
        edges = []
    if nodes is None:
        nodes = []
    node_id = f"n{len(nodes)}"
    nodes.append((node_id, _node_label(node)))

    children: list[Any] = []
    if isinstance(node, Program):
        children = node.body
    elif isinstance(node, (Assign, Print)):
        children = [node.value]
    elif isinstance(node, (If, While)):
        children = [node.condition, *node.body]
    elif isinstance(node, BinOp):
        children = [node.left, node.right]

    for child in children:
        _, child_id = _ast_edges(child, edges, nodes)
        edges.append((node_id, child_id))
    return nodes, node_id


def _ast_svg(tree: Program) -> str:
    edges: list[tuple[str, str]] = []
    nodes, _ = _ast_edges(tree, edges)
    # The recursive traversal produces a compact, deterministic left-to-right
    # layout. Each level is assigned a row, then centered within that row.
    levels: dict[int, list[tuple[str, str]]] = {}

    def collect(node: Any, depth: int = 0, node_id: str = "n0") -> None:
        levels.setdefault(depth, []).append((node_id, _node_label(node)))
        children: list[Any] = []
        if isinstance(node, Program):
            children = node.body
        elif isinstance(node, (Assign, Print)):
            children = [node.value]
        elif isinstance(node, (If, While)):
            children = [node.condition, *node.body]
        elif isinstance(node, BinOp):
            children = [node.left, node.right]
        child_ids = [child_id for parent_id, child_id in edges if parent_id == node_id]
        for child, child_id in zip(children, child_ids):
            collect(child, depth + 1, child_id)

    collect(tree)
    width = max(720, max((len(row) for row in levels.values()), default=1) * 180)
    height = max(150, len(levels) * 105)
    positions: dict[str, tuple[float, float]] = {}
    for depth, row in levels.items():
        spacing = width / (len(row) + 1)
        for index, (node_id, _) in enumerate(row, 1):
            positions[node_id] = (spacing * index, 45 + depth * 95)

    edge_markup = "".join(
        f"<line x1='{positions[parent][0]:.1f}' y1='{positions[parent][1] + 20:.1f}' "
        f"x2='{positions[child][0]:.1f}' y2='{positions[child][1] - 20:.1f}' />"
        for parent, child in edges
    )
    node_markup = "".join(
        f"<g><rect x='{x - 67:.1f}' y='{y - 20:.1f}' width='134' height='40' rx='8'/>"
        f"<text x='{x:.1f}' y='{y + 5:.1f}'>{_escape(label)}</text></g>"
        for node_id, label in nodes
        for x, y in [positions[node_id]]
    )
    return f"<svg class='ast' viewBox='0 0 {width} {height}'>{edge_markup}{node_markup}</svg>"

def _ast_tree(tree: Program) -> str:
    """Render a robust text tree; the SVG is intentionally supplemented."""
    def lines(node: Any, prefix: str = "", last: bool = True) -> list[str]:
        result = [f"{prefix}{'`- ' if last else '|- '}{_node_label(node)}"]
        children: list[Any] = []
        if isinstance(node, Program):
            children = node.body
        elif isinstance(node, (Assign, Print)):
            children = [node.value]
        elif isinstance(node, (If, While)):
            children = [node.condition, *node.body]
        elif isinstance(node, BinOp):
            children = [node.left, node.right]
        for index, child in enumerate(children):
            result.extend(lines(child, prefix + ("   " if last else "|  "), index == len(children) - 1))
        return result

    return "<pre class='tree'>" + _escape("\n".join(lines(tree))) + "</pre>"


def render_pipeline(source: str) -> str:
    """Return a self-contained HTML visualization for compiler *source*."""
    tokens: list[tuple[str, str]] = []
    lex_error: str | None = None
    parse_error: str | None = None
    generation_error: str | None = None
    generated = ""
    tree: Program | None = None
    try:
        tokens = lexer(source)
    except SyntaxError as error:
        lex_error = str(error)
    if lex_error is None:
        try:
            tree = parse(tokens)
        except SyntaxError as error:
            parse_error = str(error)
    if tree is not None:
        try:
            generated = generate(tree)
        except CodeGenerationError as error:
            generation_error = str(error)

    lexer_status = "success" if lex_error is None else "error"
    parser_status = "success" if tree is not None else ("blocked" if lex_error else "error")
    generator_status = "success" if generated or tree is not None and not generation_error else (
        "blocked" if tree is None else "error"
    )
    ast_content = (
        f"{_ast_tree(tree)}<div class='diagram'>{_ast_svg(tree)}</div>"
        if tree is not None
        else f"<div class='error'>{_escape(parse_error or 'Waiting for valid tokens')}</div>"
    )
    generator_content = (
        f"<pre class='source'>{_escape(generated)}</pre>"
        if generator_status == "success"
        else f"<div class='error'>{_escape(generation_error or 'Waiting for a valid AST')}</div>"
    )
    return _PAGE_TEMPLATE.format(
        source=_escape(source),
        lexer_status=lexer_status,
        lexer_class=_status_class(lexer_status),
        lexer_detail=_escape(lex_error or f"{len(tokens)} tokens"),
        tokens=_tokens_table(tokens),
        parser_status=parser_status,
        parser_class=_status_class(parser_status),
        parser_detail=_escape(parse_error or ("AST created" if tree else "Not run")),
        generator_status=generator_status,
        generator_class=_status_class(generator_status),
        generator_detail=_escape(
            generation_error or ("Python generated" if generated or tree is not None else "Not run")
        ),
        generator_content=generator_content,
        ast_content=ast_content,
    )


def _status_class(status: str) -> str:
    return {"success": "ok", "error": "error", "blocked": "blocked"}[status]


_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mini Compiler Pipeline Visualizer</title>
<style>
:root {{ color-scheme: dark; --bg:#111827; --panel:#1f2937; --border:#374151; --text:#f3f4f6; --muted:#9ca3af; --accent:#60a5fa; }}
* {{ box-sizing:border-box; }} body {{ margin:0; padding:32px; background:var(--bg); color:var(--text); font:15px/1.5 system-ui,sans-serif; }}
main {{ max-width:1100px; margin:auto; }} h1 {{ margin:0 0 8px; }} h2 {{ margin-top:0; font-size:1.1rem; }} .lead,.muted {{ color:var(--muted); }}
.pipeline {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin:28px 0; }} .card {{ background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:18px; }}
.card h2 {{ display:flex; justify-content:space-between; gap:12px; }} .badge {{ border-radius:999px; padding:2px 9px; font-size:.75rem; text-transform:uppercase; }}
.ok {{ background:#065f46; color:#a7f3d0; }} .error {{ background:#7f1d1d; color:#fecaca; padding:12px; border-radius:8px; }} .blocked {{ background:#78350f; color:#fde68a; }}
pre {{ white-space:pre-wrap; overflow:auto; }} code,pre {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }} .source,.tree {{ background:#0b1220; border:1px solid var(--border); border-radius:8px; padding:14px; }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ text-align:left; padding:7px 9px; border-bottom:1px solid var(--border); }} th {{ color:var(--muted); }}
.diagram {{ overflow:auto; margin-top:18px; }} .ast {{ min-width:720px; width:100%; height:auto; }} .ast line {{ stroke:#6b7280; stroke-width:2; }} .ast rect {{ fill:#2563eb; stroke:#93c5fd; }} .ast text {{ fill:white; text-anchor:middle; font-size:12px; }}
@media (max-width:760px) {{ body {{ padding:18px; }} .pipeline {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body><main>
<h1>Mini Compiler Pipeline</h1>
<p class="lead">Source → lexer tokens → parser/AST → generated Python</p>
<section class="pipeline">
<article class="card"><h2>1. Source</h2><pre class="source">{source}</pre></article>
<article class="card"><h2>2. Lexer <span class="badge {lexer_class}">{lexer_status}</span></h2><p>{lexer_detail}</p>{tokens}</article>
<article class="card"><h2>3. Parser <span class="badge {parser_class}">{parser_status}</span></h2><p>{parser_detail}</p></article>
</section>
<section class="card"><h2>4. Generated Python <span class="badge {generator_class}">{generator_status}</span></h2><p>{generator_detail}</p>{generator_content}</section>
<section class="card"><h2>Abstract Syntax Tree</h2>{ast_content}</section>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize the mini-compiler pipeline as HTML.")
    parser.add_argument("source", type=Path, help="Source file to visualize")
    parser.add_argument("-o", "--output", type=Path, help="HTML output path")
    parser.add_argument("--open", action="store_true", help="Open the generated HTML in a browser")
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    output = args.output or Path(tempfile.gettempdir()) / "mini-compiler-pipeline.html"
    output.write_text(render_pipeline(source), encoding="utf-8")
    print(f"Pipeline visualization written to {output}")
    if args.open:
        webbrowser.open(output.resolve().as_uri())


if __name__ == "__main__":
    main()

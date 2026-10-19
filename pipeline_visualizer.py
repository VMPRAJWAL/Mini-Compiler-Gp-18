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
        f"<tr><td class='token-index'>{index:02}</td>"
        f"<td><span class='token-chip token-{_escape(token_type).lower()}'>{_escape(token_type)}</span></td>"
        f"<td><code>{_escape(text or '∅')}</code></td></tr>"
        for index, (token_type, text) in enumerate(tokens)
    )
    return (
        "<table><thead><tr><th>#</th><th>Type</th><th>Text</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _source_listing(source: str) -> str:
    lines = source.splitlines() or [""]
    return "".join(
        f"<span class='source-line'><span class='line-number'>{index:02}</span>"
        f"<span>{_escape(line) or '&nbsp;'}</span></span>"
        for index, line in enumerate(lines, 1)
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

    return (
        "<div class='tree-wrap'><span class='annotation tree-note'>shape of the program</span>"
        "<pre class='tree'>" + _escape("\n".join(lines(tree))) + "</pre></div>"
    )


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
    overall_status = (
        "success"
        if all(status == "success" for status in (lexer_status, parser_status, generator_status))
        else "attention"
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
        source_listing=_source_listing(source),
        source_lines=len(source.splitlines() or [""]),
        token_count=len(tokens),
        lexer_status=lexer_status,
        lexer_class=_status_class(lexer_status),
        lexer_detail=_escape(lex_error or "DFA scan complete"),
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
        overall_status=overall_status,
        overall_class="ok" if overall_status == "success" else "warn",
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
:root {{ --paper:#f5f0e6; --cream:#fbf8f1; --forest:#20392d; --olive:#777b68; --terracotta:#c66f4b; --sage:#a5ae91; --taupe:#d8cebd; --success:#477a5b; --brick:#b94d40; --ink:#2c382e; }}
* {{ box-sizing:border-box; }} body {{ margin:0; min-width:320px; background:var(--paper); color:var(--forest); font:15px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif; }}
body::before {{ background-image:radial-gradient(rgba(32,57,45,.08) .7px,transparent .7px); background-size:9px 9px; content:""; inset:0; opacity:.18; pointer-events:none; position:fixed; }}
main {{ margin:auto; max-width:1220px; padding:38px 28px 68px; position:relative; }} h1,h2,p {{ margin-top:0; }} h1,h2 {{ font-family:Georgia,"Times New Roman",serif; font-weight:500; }} h1 {{ font-size:clamp(2.5rem,6vw,5rem); letter-spacing:-.055em; line-height:.98; margin-bottom:12px; }} h2 {{ font-size:1.35rem; }} .muted,.lead {{ color:var(--olive); }} .lead {{ font-size:1.05rem; max-width:560px; }}
.topbar {{ align-items:flex-start; display:flex; justify-content:space-between; gap:24px; margin-bottom:35px; }} .eyebrow,.stage-number,.panel-kicker {{ color:var(--terracotta); font-size:.7rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }} .eyebrow {{ margin-bottom:17px; }} .annotation {{ color:var(--terracotta); font-family:"Comic Sans MS","Bradley Hand",cursive; font-size:.95rem; }} .hero-note {{ display:block; margin:20px 0 0 210px; transform:rotate(-3deg); }} .overall {{ align-items:center; background:var(--cream); border:1px solid var(--taupe); border-radius:3px 12px 4px 12px; box-shadow:3px 4px 0 rgba(32,57,45,.08); display:flex; gap:10px; padding:12px 15px; transform:rotate(1deg); white-space:nowrap; }} .dot {{ background:var(--success); border-radius:50%; height:9px; width:9px; }} .dot.warn {{ background:var(--terracotta); }}
.pipeline {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:22px; margin:0 0 30px; }} .stage {{ background:var(--cream); border:1px solid var(--taupe); border-radius:4px 15px 5px 13px; min-height:128px; padding:18px; position:relative; box-shadow:2px 4px 0 rgba(32,57,45,.045); }} .stage:not(:last-child)::after {{ color:var(--terracotta); content:'↝'; font-family:cursive; font-size:25px; line-height:1; position:absolute; right:-27px; top:50%; transform:translateY(-50%); z-index:2; }} .stage-number {{ color:var(--olive); }} .stage-title {{ align-items:center; display:flex; gap:8px; justify-content:space-between; margin:15px 0 5px; }} .stage-title h2 {{ font-size:1.12rem; margin:0; }} .stage-detail {{ color:var(--olive); font-size:.79rem; margin:0; }}
.badge {{ border:1px solid currentColor; border-radius:999px; font-size:.64rem; font-weight:800; letter-spacing:.06em; padding:3px 8px; text-transform:uppercase; }} .ok {{ color:var(--success); }} .warn {{ color:var(--terracotta); }} .error {{ background:#f8e4df; border:1px solid #df9f91; border-radius:5px 12px 5px 12px; color:var(--brick); padding:12px; }} .blocked {{ color:#9a7624; }}
.panel {{ background:rgba(251,248,241,.88); border:1px solid var(--taupe); border-radius:5px 16px 6px 14px; box-shadow:3px 5px 0 rgba(32,57,45,.045); padding:22px; }} .panel + .panel {{ margin-top:22px; }} .panel-header {{ align-items:flex-start; display:flex; justify-content:space-between; gap:16px; margin-bottom:17px; }} .panel-title {{ margin:0 0 3px; }} .panel-subtitle {{ color:var(--olive); font-size:.84rem; margin:0; }}
.source-layout {{ display:grid; grid-template-columns:minmax(0,1.15fr) minmax(240px,.85fr); gap:18px; }} .code-window {{ background:#f8f5ed; border:1px solid var(--taupe); border-radius:4px 12px 4px 10px; overflow:hidden; }} .window-bar {{ align-items:center; border-bottom:1px solid var(--taupe); display:flex; gap:7px; padding:10px 13px; }} .window-dot {{ background:var(--sage); border-radius:50%; height:8px; width:8px; }} .window-label {{ color:var(--olive); font-size:.75rem; margin-left:5px; }} .source-code {{ display:block; max-height:360px; overflow:auto; padding:14px 0; }} .source-line {{ display:grid; grid-template-columns:42px minmax(0,1fr); min-height:24px; padding:0 16px 0 0; white-space:pre; }} .line-number {{ color:#aaa38f; padding-right:14px; text-align:right; user-select:none; }}
.stats {{ display:grid; grid-template-columns:repeat(2,1fr); gap:10px; align-content:start; }} .stat {{ background:var(--paper); border:1px solid var(--taupe); border-radius:3px 10px 3px 9px; padding:15px; }} .stat-value {{ display:block; font-family:Georgia,serif; font-size:1.6rem; }} .stat-label {{ color:var(--olive); font-size:.72rem; }}
pre {{ white-space:pre-wrap; overflow:auto; }} code,pre {{ font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace; }} .generated {{ background:#f8f5ed; border:1px solid var(--taupe); border-radius:4px 12px 4px 10px; color:var(--ink); margin:0; padding:18px; }} .tree-wrap {{ position:relative; }} .tree-note {{ display:block; margin:0 0 7px 12px; transform:rotate(-2deg); }} .tree {{ background:#f8f5ed; border:1px solid var(--taupe); border-radius:4px 12px 4px 10px; color:var(--forest); margin:0; padding:16px; }}
table {{ border-collapse:collapse; width:100%; }} .token-table {{ max-height:310px; overflow:auto; }} th,td {{ border-bottom:1px solid #e5ddcf; padding:9px 10px; text-align:left; }} th {{ background:#f3ede1; color:var(--olive); font-size:.7rem; position:sticky; text-transform:uppercase; top:0; }} td {{ color:var(--ink); font-size:.82rem; }} tbody tr:hover {{ background:#f5efe5; }} td code {{ color:var(--forest); }} .token-index {{ color:#aaa38f; font-size:.72rem; }} .token-chip {{ border:1px solid var(--sage); border-radius:999px; color:var(--forest); display:inline-block; font-size:.66rem; font-weight:800; letter-spacing:.04em; padding:2px 7px; }} .token-keyword,.token-print,.token-if,.token-while,.token-end {{ border-color:var(--terracotta); color:#a55539; }} .token-num {{ border-color:var(--sage); }} .token-op,.token-eq,.token-neq,.token-lt,.token-gt {{ border-color:#9aa879; color:#5d704a; }}
.ast-layout {{ display:grid; grid-template-columns:minmax(240px,.7fr) minmax(0,1.3fr); gap:18px; }} .diagram {{ align-items:center; background:#f8f5ed; border:1px solid var(--taupe); border-radius:4px 12px 4px 10px; display:flex; min-height:220px; overflow:auto; padding:14px; }} .ast {{ min-width:720px; width:100%; }} .ast line {{ stroke:#9aa18a; stroke-width:2; }} .ast rect {{ fill:#e9eee0; stroke:var(--sage); }} .ast text {{ fill:var(--forest); font-size:12px; text-anchor:middle; }}
@media (max-width:900px) {{ .pipeline {{ grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }} .stage:not(:last-child)::after {{ display:none; }} .source-layout,.ast-layout {{ grid-template-columns:1fr; }} }} @media (max-width:600px) {{ main {{ padding:27px 16px 45px; }} .topbar {{ display:block; }} .overall {{ display:inline-flex; margin-bottom:22px; }} .hero-note {{ margin-left:80px; }} .pipeline {{ grid-template-columns:1fr; }} .stage {{ min-height:auto; }} }}
@media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ scroll-behavior:auto!important; transition:none!important; }} }}
</style>
</head>
<body><main>
<header class="topbar"><div><div class="eyebrow">A little compiler lab</div><h1>From source<br>to syntax.</h1><p class="lead">Follow every character, token, and syntax tree as your code becomes executable Python.</p><span class="annotation hero-note">watch the transformation ↗</span></div><div class="overall" role="status" aria-live="polite"><span class="dot {overall_class}"></span><strong>{overall_status}</strong><span class="muted">pipeline</span></div></header>
<nav class="pipeline" aria-label="Compiler stages">
<article class="stage"><span class="stage-number">01 / INPUT</span><div class="stage-title"><h2>Source</h2><span class="badge ok">ready</span></div><p class="stage-detail">{source_lines} lines</p></article>
<article class="stage"><span class="stage-number">02 / SCAN</span><div class="stage-title"><h2>Lexer</h2><span class="badge {lexer_class}">{lexer_status}</span></div><p class="stage-detail">{token_count} tokens · {lexer_detail}</p></article>
<article class="stage"><span class="stage-number">03 / PARSE</span><div class="stage-title"><h2>Parser + AST</h2><span class="badge {parser_class}">{parser_status}</span></div><p class="stage-detail">{parser_detail}</p></article>
<article class="stage"><span class="stage-number">04 / EMIT</span><div class="stage-title"><h2>Python</h2><span class="badge {generator_class}">{generator_status}</span></div><p class="stage-detail">{generator_detail}</p></article>
</nav>
<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Source input</h2><p class="panel-subtitle">The mini-language program being compiled.</p></div></div><div class="source-layout"><div class="code-window"><div class="window-bar"><span class="window-dot"></span><span class="window-dot"></span><span class="window-dot"></span><span class="window-label">program.mc</span></div><pre class="source-code">{source_listing}</pre></div><div class="stats"><div class="stat"><span class="stat-value">{source_lines}</span><span class="stat-label">source lines</span></div><div class="stat"><span class="stat-value">{token_count}</span><span class="stat-label">tokens emitted</span></div></div></div></section>
<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Token stream</h2><p class="panel-subtitle">Maximal-munch output from the DFA lexer.</p></div></div><div class="token-table">{tokens}</div></section>
<section class="panel"><div class="panel-header"><div><span class="panel-kicker">stage four / emit</span><h2 class="panel-title">Generated Python</h2><p class="panel-subtitle">{generator_detail}</p></div><span class="annotation">ready to run ↗</span></div>{generator_content}</section>
<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Abstract syntax tree</h2><p class="panel-subtitle">The structure produced by the recursive-descent parser.</p></div></div>{ast_content}</section>
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

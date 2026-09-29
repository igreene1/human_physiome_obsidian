#!/usr/bin/env python3
"""Check Obsidian links, metadata and Canvas structure without network access.

Run: python3 '90 Maintenance/validate_vault.py'
Optional: --root PATH --report PATH
PyYAML, when installed, enables an additional full YAML syntax check.
This validates document structure, not biological accuracy or completeness.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote


def validate(root: Path) -> dict:
    errors = []
    warnings = []
    files = sorted(p for p in root.rglob('*') if p.is_file())
    notes = [p for p in files if p.suffix == '.md']
    canvases = [p for p in files if p.suffix == '.canvas']
    paths = {p.relative_to(root).as_posix(): p for p in files}
    stems = defaultdict(list)
    names = defaultdict(list)
    texts = {}
    headings = {}
    graph = defaultdict(set)
    counts = Counter(markdown=len(notes), canvas=len(canvases))

    def error(kind, source, detail):
        errors.append({'kind': kind, 'source': source, 'detail': detail})

    for rel, p in paths.items():
        names[p.name].append(rel)
        if p.suffix == '.md':
            stems[p.stem].append(rel)
    for key, values in stems.items():
        if len(values) > 1:
            error('ambiguous_note_name', key, values)
    folded = defaultdict(list)
    for rel in paths:
        folded[rel.casefold()].append(rel)
    for values in folded.values():
        if len(values) > 1:
            error('case_collision', values[0], values)
    for rel in paths:
        if any(re.search(r'[<>:"|?*]', part) or part.endswith(('.', ' '))
               for part in Path(rel).parts):
            error('nonportable_filename', rel, 'Windows-incompatible path')

    try:
        import yaml
    except ImportError:
        yaml = None
        warnings.append('PyYAML is not installed; frontmatter delimiters are checked, but full YAML parsing is skipped.')

    for p in notes:
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeError as exc:
            error('text_encoding', rel, str(exc))
            continue
        texts[rel] = text
        if not text.startswith('---\n') or '\n---\n' not in text[4:]:
            error('frontmatter', rel, 'Missing YAML frontmatter delimiters')
        elif yaml:
            try:
                meta = yaml.safe_load(text[4:].split('\n---\n', 1)[0])
                if not isinstance(meta, dict) or not meta.get('title') or not meta.get('type'):
                    error('frontmatter', rel, 'Missing title or type')
                else:
                    counts['yaml_parsed'] += 1
                    if meta['title'] != p.stem:
                        error('title_filename_mismatch', rel, meta['title'])
                    if meta.get('type') == 'reaction':
                        counts['reactions'] += 1
                    if meta.get('type') == 'cell-type':
                        counts['cell_types'] += 1
            except Exception as exc:
                error('yaml_syntax', rel, str(exc))
        if '\ufffd' in text or '\u0393\u00c7' in text:
            error('encoding_artifact', rel, 'Replacement character or original mojibake pattern')
        if '\\n' in text:
            error('escaped_newline', rel, 'Literal backslash-n in Markdown')
        if text.count('[[') != text.count(']]'):
            error('wiki_delimiters', rel, 'Unbalanced wiki-link delimiters')
        headings[rel] = {
            re.sub(r'[*_`]', '', h).strip().rstrip('#').strip()
            for h in re.findall(r'^#{1,6}\s+(.+)$', text, re.M)
        }

    def resolve(raw, source):
        raw = unquote(raw.strip()).replace('\\', '/')
        if not raw:
            return source
        options = []
        for candidate in (raw, raw + '.md'):
            if candidate in paths:
                options.append(candidate)
        if not options:
            candidate = (Path(source).parent / raw).as_posix()
            for value in (candidate, candidate + '.md'):
                if value in paths:
                    options.append(value)
        if not options:
            options = names.get(raw, []) if Path(raw).suffix else stems.get(raw, [])
        if not options and '/' in raw:
            options = [rel for rel in paths if rel.endswith('/' + raw)
                       or rel.endswith('/' + raw + '.md')]
        options = sorted(set(options))
        if len(options) == 1:
            return options[0]
        error('missing_link' if not options else 'ambiguous_link', source, raw)
        return None

    def anchor_ok(target, anchor, source):
        if not anchor or target not in texts:
            return
        anchor = unquote(anchor)
        if anchor.startswith('^'):
            valid = re.search(r'\^' + re.escape(anchor[1:]) + r'\s*$', texts[target], re.M)
        else:
            parts = [re.sub(r'[*_`]', '', s).strip() for s in anchor.split('#')]
            valid = all(part in headings[target] for part in parts)
        if not valid:
            error('missing_anchor', source, target + '#' + anchor)

    for rel, text in texts.items():
        for match in re.finditer(r'\[\[([^\]\n]+)\]\]', text):
            counts['wiki_links'] += 1
            target = match.group(1).split('|', 1)[0]
            target, _, anchor = target.partition('#')
            resolved = resolve(target, rel)
            if resolved:
                graph[rel].add(resolved)
                anchor_ok(resolved, anchor, rel)
        for match in re.finditer(r'(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)', text):
            target = match.group(1).strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                counts['external_reference_links'] += 1
                continue
            if not target or target.startswith('#'):
                continue
            counts['local_markdown_links'] += 1
            resolved = resolve(target.split('#', 1)[0], rel)
            if resolved:
                graph[rel].add(resolved)

    for p in canvases:
        rel = p.relative_to(root).as_posix()
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError) as exc:
            error('canvas_json', rel, str(exc))
            continue
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])
        if not isinstance(nodes, list) or not isinstance(edges, list):
            error('canvas_schema', rel, 'nodes and edges must be arrays')
            continue
        node_ids = [n.get('id') for n in nodes]
        edge_ids = [e.get('id') for e in edges]
        for kind, ids in [('node', node_ids), ('edge', edge_ids)]:
            if None in ids or len(ids) != len(set(ids)):
                error('canvas_ids', rel, 'Missing or duplicate ' + kind + ' IDs')
        for n in nodes:
            counts['canvas_nodes'] += 1
            if n.get('type') not in {'text', 'file', 'link', 'group'}:
                error('canvas_node_type', rel, n.get('type'))
            if not all(isinstance(n.get(k), (int, float)) for k in ('x', 'y', 'width', 'height')):
                error('canvas_geometry', rel, n.get('id'))
            elif n['width'] <= 0 or n['height'] <= 0:
                error('canvas_geometry', rel, 'Nonpositive card dimensions')
            if n.get('type') == 'file':
                counts['canvas_file_references'] += 1
                target = n.get('file')
                if target not in paths:
                    error('canvas_file', rel, target)
                else:
                    graph[rel].add(target)
                    anchor_ok(target, n.get('subpath', '').lstrip('#'), rel)
        for edge in edges:
            counts['canvas_edges'] += 1
            if edge.get('fromNode') not in node_ids or edge.get('toNode') not in node_ids:
                error('canvas_edge', rel, edge.get('id'))
            for field in ('fromSide', 'toSide'):
                if field in edge and edge[field] not in {'top', 'right', 'bottom', 'left'}:
                    error('canvas_edge_side', rel, edge.get('id'))
            for field in ('fromEnd', 'toEnd'):
                if field in edge and edge[field] not in {'none', 'arrow'}:
                    error('canvas_edge_end', rel, edge.get('id'))
        if rel.startswith('39 Visual Maps/') or p.name == 'Human Body — Master Map.canvas':
            counts['new_or_rebuilt_canvases'] += 1
            cards = [n for n in nodes if n.get('type') != 'group']
            for i, a in enumerate(cards):
                for b in cards[i + 1:]:
                    if (a['x'] < b['x'] + b['width'] and b['x'] < a['x'] + a['width']
                            and a['y'] < b['y'] + b['height'] and b['y'] < a['y'] + a['height']):
                        error('canvas_card_overlap', rel, [a['id'], b['id']])

    start = '00 START HERE.md'
    visited = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for target in graph[current]:
            if target not in visited:
                visited.add(target)
                queue.append(target)
    content_paths = {p.relative_to(root).as_posix() for p in notes + canvases}
    unreachable = sorted(content_paths - visited)
    counts['reachable_notes_and_canvases'] = len(content_paths & visited)
    for rel in unreachable:
        error('unreachable_from_start', rel, 'No navigation route from 00 START HERE')
    return {'status': 'pass' if not errors else 'fail', 'counts': dict(counts),
            'errors': errors, 'warnings': warnings,
            'scope': 'Local document structure only; no biological accuracy, external URL availability or native Obsidian rendering certification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = validate(args.root.resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())

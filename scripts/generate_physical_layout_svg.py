#!/usr/bin/env python3
import argparse
import html
import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Key:
    width: float
    height: float
    x: float
    y: float
    rotation: float
    rx: float
    ry: float
    row: int | None = None
    col: int | None = None


@dataclass
class Module:
    label: str
    display_name: str
    module_type: str
    width: float
    height: float
    x: float
    y: float
    rotation: float = 0
    rx: float = 0
    ry: float = 0
    shape: str = "rect"


@dataclass
class Binding:
    tap: str
    hold: str = ""
    css_class: str = ""


@dataclass
class Layer:
    name: str
    label: str
    bindings: list[Binding]


@dataclass
class Combo:
    name: str
    binding: Binding
    positions: list[int]
    layers: list[int] | None = None


def find_labeled_block(text, label):
    match = re.search(rf"\b{re.escape(label)}\s*:\s*[A-Za-z0-9_,@-]+\s*\{{", text)
    if not match:
        raise SystemExit(f"Could not find node label: {label}")

    start = match.end()
    depth = 1
    index = start
    while index < len(text) and depth:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1

    if depth:
        raise SystemExit(f"Unclosed node block for label: {label}")
    return text[start : index - 1]


def try_find_labeled_block(text, label):
    try:
        return find_labeled_block(text, label)
    except SystemExit:
        return None


def find_named_block(text, name):
    match = re.search(rf"\b{re.escape(name)}\s*\{{", text)
    if not match:
        raise SystemExit(f"Could not find node: {name}")

    start = match.end()
    depth = 1
    index = start
    while index < len(text) and depth:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1

    if depth:
        raise SystemExit(f"Unclosed node block for: {name}")
    return text[start : index - 1]


def iter_child_blocks(text):
    index = 0
    pattern = re.compile(r"\b([A-Za-z0-9_]+)\s*\{")
    while True:
        match = pattern.search(text, index)
        if not match:
            break

        name = match.group(1)
        start = match.end()
        depth = 1
        cursor = start
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1

        if depth:
            raise SystemExit(f"Unclosed node block for: {name}")
        yield name, text[start : cursor - 1]
        index = cursor


def find_first_physical_layout_label(text):
    for match in re.finditer(r"\b([A-Za-z0-9_]+)\s*:\s*[A-Za-z0-9_,@-]+\s*\{", text):
        block = find_labeled_block(text, match.group(1))
        if re.search(r'compatible\s*=\s*"zmk,physical-layout"', block):
            return match.group(1)
    raise SystemExit("Could not find a zmk,physical-layout node")


def iter_labeled_blocks(text):
    index = 0
    pattern = re.compile(r"\b([A-Za-z0-9_]+)\s*:\s*[A-Za-z0-9_,@-]+\s*\{")
    while True:
        match = pattern.search(text, index)
        if not match:
            break

        label = match.group(1)
        start = match.end()
        depth = 1
        cursor = start
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1

        if depth:
            raise SystemExit(f"Unclosed node block for label: {label}")
        yield label, text[start : cursor - 1]
        index = cursor


def clean_number(value):
    number = int(value.strip("()")) if isinstance(value, str) else value
    return number / 100


def parse_int_property(block, name, default=None):
    match = re.search(rf"\b{re.escape(name)}\s*=\s*<\s*(\(?-?\d+\)?)\s*>", block)
    if not match:
        return default
    return clean_number(match.group(1))


def parse_string_property(block, name, default=""):
    match = re.search(rf'\b{re.escape(name)}\s*=\s*"([^"]*)"', block)
    return match.group(1) if match else default


def parse_display_name(layout_block, fallback):
    match = re.search(r'\bdisplay-name\s*=\s*"([^"]+)"\s*;', layout_block)
    return match.group(1) if match else fallback


def parse_key_attrs(layout_block):
    keys_match = re.search(r"\bkeys\b.*?=\s*(.*?);", layout_block, re.S)
    if not keys_match:
        raise SystemExit("Could not find physical layout keys")

    keys = []
    for match in re.finditer(
        r"<\s*&key_physical_attrs\s+(\(?-?\d+\)?)\s+(\(?-?\d+\)?)\s+(\(?-?\d+\)?)\s+(\(?-?\d+\)?)\s+(\(?-?\d+\)?)\s+(\(?-?\d+\)?)\s+(\(?-?\d+\)?)\s*>",
        keys_match.group(1),
    ):
        width, height, x, y, rotation, rx, ry = (
            clean_number(value) for value in match.groups()
        )
        keys.append(Key(width, height, x, y, rotation, rx, ry))

    if not keys:
        raise SystemExit("No key_physical_attrs entries found")
    return keys


def parse_modules(text):
    modules = []
    for label, block in iter_labeled_blocks(text):
        if re.search(r'\bstatus\s*=\s*"disabled"\s*;', block):
            continue

        compat_match = re.search(r'\bcompatible\s*=\s*"([^"]+)"\s*;', block)
        if not compat_match:
            continue

        compatible = compat_match.group(1)
        display_name = parse_string_property(block, "display-name", label)

        if compatible == "zmk,physical-layout-custom-module":
            width = parse_int_property(block, "width")
            height = parse_int_property(block, "height")
            x = parse_int_property(block, "x")
            y = parse_int_property(block, "y")
            if None in {width, height, x, y}:
                continue
            modules.append(
                Module(
                    label=label,
                    display_name=display_name,
                    module_type=parse_string_property(block, "type", "custom"),
                    width=width,
                    height=height,
                    x=x,
                    y=y,
                    rotation=parse_int_property(block, "r", 0),
                    rx=parse_int_property(block, "rx", 0),
                    ry=parse_int_property(block, "ry", 0),
                )
            )
        elif compatible == "zmk,physical-layout-trackball":
            size = parse_int_property(block, "size")
            x = parse_int_property(block, "x")
            y = parse_int_property(block, "y")
            if None in {size, x, y}:
                continue
            modules.append(
                Module(
                    label=label,
                    display_name=display_name,
                    module_type="trackball",
                    width=size,
                    height=size,
                    x=x,
                    y=y,
                    shape="circle",
                )
            )
        elif compatible in {
            "zmk,physical-layout-touch-pad",
            "zmk,physical-layout-rotary-encoder",
        }:
            if compatible == "zmk,physical-layout-rotary-encoder":
                size = parse_int_property(block, "size")
                width = height = size
                shape = "circle"
                module_type = "rotary-encoder"
            else:
                width = parse_int_property(block, "width")
                height = parse_int_property(block, "height")
                shape = "rect"
                module_type = "touch-pad"

            x = parse_int_property(block, "x")
            y = parse_int_property(block, "y")
            if None in {width, height, x, y}:
                continue
            modules.append(
                Module(
                    label=label,
                    display_name=display_name,
                    module_type=module_type,
                    width=width,
                    height=height,
                    x=x,
                    y=y,
                    rotation=parse_int_property(block, "r", 0),
                    rx=parse_int_property(block, "rx", 0),
                    ry=parse_int_property(block, "ry", 0),
                    shape=shape,
                )
            )

    return modules


def parse_transform_positions(text, layout_block):
    transform_match = re.search(r"transform\s*=\s*<\s*&([A-Za-z0-9_]+)\s*>", layout_block)
    if not transform_match:
        return []

    transform_block = find_labeled_block(text, transform_match.group(1))
    map_match = re.search(r"\bmap\b\s*=\s*<(.*?)>;", transform_block, re.S)
    if not map_match:
        return []

    return [
        (int(row), int(col))
        for row, col in re.findall(r"RC\(\s*(\d+)\s*,\s*(\d+)\s*\)", map_match.group(1))
    ]


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*", "", text)


def resolve_include_path(include_name, delimiter, source_path):
    include_path = Path(include_name)
    if include_path.is_absolute() and include_path.exists():
        return include_path

    candidates = [source_path.parent / include_name, Path.cwd() / include_name]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Angle includes often point to dt-bindings or module-provided helper files
    # that are not needed for this lightweight layout parser.
    if delimiter == "<":
        return None

    raise SystemExit(f"Could not resolve include {include_name!r} from {source_path}")


def read_devicetree_with_includes(input_path, include_stack=None):
    source_path = input_path.resolve()
    include_stack = include_stack or []
    if source_path in include_stack:
        chain = " -> ".join(str(path) for path in [*include_stack, source_path])
        raise SystemExit(f"Recursive devicetree include detected: {chain}")

    text = source_path.read_text(encoding="utf-8-sig")
    expanded_lines = []
    include_pattern = re.compile(r'^\s*#include\s+([<"])([^>"]+)[>"]')
    next_stack = [*include_stack, source_path]

    for line in text.splitlines():
        match = include_pattern.match(line)
        if not match:
            expanded_lines.append(line)
            continue

        delimiter, include_name = match.groups()
        include_path = resolve_include_path(include_name, delimiter, source_path)
        if include_path is None:
            expanded_lines.append(line)
            continue

        expanded_lines.append(f"/* begin include {include_name} */")
        expanded_lines.append(read_devicetree_with_includes(include_path, next_stack))
        expanded_lines.append(f"/* end include {include_name} */")

    return "\n".join(expanded_lines)


def parse_binding_groups(bindings_text):
    tokens = strip_comments(bindings_text).replace("<", " ").replace(">", " ").split()
    groups = []
    current = []
    for token in tokens:
        if token.startswith("&"):
            if current:
                groups.append(current)
            current = [token]
        elif current:
            current.append(token)
    if current:
        groups.append(current)
    return groups


def friendly_keycode(value):
    aliases = {
        "BACKSPACE": "BKSP",
        "RETURN": "ENTER",
        "ESCAPE": "ESC",
        "DELETE": "DEL",
        "MINUS": "-",
        "EQUAL": "=",
        "LBKT": "[",
        "RBKT": "]",
        "BSLH": "\\",
        "FSLH": "/",
        "SEMI": ";",
        "SQT": "'",
        "GRAVE": "`",
        "COMMA": ",",
        "DOT": ".",
        "SPACE": "SPC",
        "LANGUAGE_1": "LANG1",
        "LANGUAGE_2": "LANG2",
    }
    if re.fullmatch(r"N\d", value):
        return value[1]
    return aliases.get(value, value)


def format_binding(group):
    if not group:
        return Binding("")

    behavior = group[0].removeprefix("&")
    args = group[1:]
    if behavior == "trans":
        return Binding("TRANS", css_class="transparent")
    if behavior == "none":
        return Binding("NONE", css_class="none")
    if behavior == "kp":
        return Binding(friendly_keycode(args[0]) if args else "")
    if behavior == "mkp":
        return Binding(friendly_keycode(args[0]) if args else "", "MOUSE")
    if behavior == "mt":
        tap = friendly_keycode(args[-1]) if args else ""
        hold = "+".join(friendly_keycode(arg) for arg in args[:-1])
        return Binding(tap, hold)
    if behavior == "lt":
        layer = args[0] if args else ""
        tap = friendly_keycode(args[1]) if len(args) > 1 else ""
        return Binding(tap, f"LT {layer}")
    if behavior in {"mo", "to", "tog"}:
        return Binding(f"{behavior.upper()} {args[0]}" if args else behavior.upper())
    if behavior == "bt":
        return Binding(" ".join(args), "BT")
    if args:
        return Binding(" ".join(friendly_keycode(arg) for arg in args), behavior)
    return Binding(behavior)


def parse_keymap_layers(keymap_path):
    keymap_text = keymap_path.read_text()
    keymap_block = find_named_block(keymap_text, "keymap")
    layers = []
    for name, block in iter_child_blocks(keymap_block):
        bindings_match = re.search(r"\bbindings\b\s*=\s*<(.*?)>;", block, re.S)
        if not bindings_match:
            continue
        label_match = re.search(r'\blabel\s*=\s*"([^"]+)"\s*;', block)
        label = label_match.group(1) if label_match else name
        groups = parse_binding_groups(bindings_match.group(1))
        layers.append(Layer(name, label, [format_binding(group) for group in groups]))

    if not layers:
        raise SystemExit(f"No keymap layers with bindings found in {keymap_path}")
    return layers


def parse_int_list_property(block, name):
    match = re.search(rf"\b{re.escape(name)}\s*=\s*<(.*?)>;", block, re.S)
    if not match:
        return None
    return [int(value) for value in re.findall(r"-?\d+", strip_comments(match.group(1)))]


def parse_keymap_combos(keymap_path):
    keymap_text = keymap_path.read_text()
    try:
        combos_block = find_named_block(keymap_text, "combos")
    except SystemExit:
        return []

    combos = []
    for name, block in iter_child_blocks(combos_block):
        positions = parse_int_list_property(block, "key-positions")
        if not positions:
            continue

        bindings_match = re.search(r"\bbindings\b\s*=\s*<(.*?)>;", block, re.S)
        binding_groups = (
            parse_binding_groups(bindings_match.group(1)) if bindings_match else []
        )
        binding = format_binding(binding_groups[0]) if binding_groups else Binding(name)
        combos.append(
            Combo(
                name=name,
                binding=binding,
                positions=positions,
                layers=parse_int_list_property(block, "layers"),
            )
        )

    return combos


def apply_positions(keys, positions):
    if not positions:
        return
    if len(positions) != len(keys):
        print(
            f"Warning: transform position count ({len(positions)}) does not match key count ({len(keys)}); row/col labels will be partial."
        )
    for key, (row, col) in zip(keys, positions):
        key.row = row
        key.col = col


def rotate_point(x, y, angle_degrees, origin_x, origin_y):
    if angle_degrees == 0:
        return x, y
    angle = math.radians(angle_degrees)
    dx = x - origin_x
    dy = y - origin_y
    return (
        origin_x + dx * math.cos(angle) - dy * math.sin(angle),
        origin_y + dx * math.sin(angle) + dy * math.cos(angle),
    )


def key_corners(key):
    points = [
        (key.x, key.y),
        (key.x + key.width, key.y),
        (key.x + key.width, key.y + key.height),
        (key.x, key.y + key.height),
    ]
    return [rotate_point(x, y, key.rotation, key.rx, key.ry) for x, y in points]


def module_corners(module):
    points = [
        (module.x, module.y),
        (module.x + module.width, module.y),
        (module.x + module.width, module.y + module.height),
        (module.x, module.y + module.height),
    ]
    return [
        rotate_point(x, y, module.rotation, module.rx, module.ry)
        for x, y in points
    ]


def layout_bounds(keys, modules):
    points = [point for key in keys for point in key_corners(key)]
    points.extend(point for module in modules for point in module_corners(module))
    min_x = min(x for x, _ in points)
    min_y = min(y for _, y in points)
    max_x = max(x for x, _ in points)
    max_y = max(y for _, y in points)
    return min_x, min_y, max_x, max_y


def px(value):
    rounded = round(value, 3)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.3f}".rstrip("0").rstrip(".")


def transform_key(key, min_x, min_y, scale, padding_x, padding_y):
    x = (key.x - min_x) * scale + padding_x
    y = (key.y - min_y) * scale + padding_y
    rx = (key.rx - min_x) * scale + padding_x
    ry = (key.ry - min_y) * scale + padding_y
    return x, y, rx, ry


def transform_key_center(key, min_x, min_y, scale, padding_x, padding_y):
    center_x = key.x + key.width / 2
    center_y = key.y + key.height / 2
    center_x, center_y = rotate_point(center_x, center_y, key.rotation, key.rx, key.ry)
    return (
        (center_x - min_x) * scale + padding_x,
        (center_y - min_y) * scale + padding_y,
    )


def transform_module(module, min_x, min_y, scale, padding_x, padding_y):
    x = (module.x - min_x) * scale + padding_x
    y = (module.y - min_y) * scale + padding_y
    rx = (module.rx - min_x) * scale + padding_x
    ry = (module.ry - min_y) * scale + padding_y
    return x, y, rx, ry


def render_key_text(binding, key_width, key_height):
    if binding is None:
        return []

    tap = html.escape(binding.tap)
    hold = html.escape(binding.hold)
    lines = [
        f'<text class="tap" x="{px(key_width / 2)}" y="{px(key_height / 2 - (6 if hold else 0))}">{tap}</text>'
    ]
    if hold:
        lines.append(
            f'<text class="hold" x="{px(key_width / 2)}" y="{px(key_height / 2 + 11)}">{hold}</text>'
        )
    return lines


def render_modules(lines, modules, min_x, min_y, key_unit_px, padding, header_height):
    for index, module in enumerate(modules):
        x, y, rx, ry = transform_module(
            module, min_x, min_y, key_unit_px, padding, padding + header_height
        )
        module_width = module.width * key_unit_px
        module_height = module.height * key_unit_px
        group_transform = (
            f'translate({px(x)} {px(y)}) rotate({px(module.rotation)} {px(rx - x)} {px(ry - y)})'
        )
        css_type = re.sub(r"[^A-Za-z0-9_-]+", "-", module.module_type)
        lines.append(
            f'<g class="module module-{css_type} modulepos-{index}" transform="{group_transform}">'
        )
        if module.shape == "circle":
            radius = min(module_width, module_height) / 2
            lines.append(
                f'<circle cx="{px(module_width / 2)}" cy="{px(module_height / 2)}" r="{px(radius)}"/>'
            )
        else:
            lines.append(
                f'<rect x="0" y="0" width="{px(module_width)}" height="{px(module_height)}" rx="10" ry="10"/>'
            )
        lines.append(
            f'<text class="module-label" x="{px(module_width / 2)}" y="{px(module_height / 2 - 6)}">{html.escape(module.display_name)}</text>'
        )
        lines.append(
            f'<text class="module-type" x="{px(module_width / 2)}" y="{px(module_height / 2 + 9)}">{html.escape(module.module_type)}</text>'
        )
        lines.append("</g>")


def combo_label(combo):
    if combo.binding.hold:
        return f"{combo.binding.hold} {combo.binding.tap}".strip()
    return combo.binding.tap or combo.name


def render_combos(
    lines,
    combos,
    keys,
    layer_index,
    min_x,
    min_y,
    key_unit_px,
    padding,
    header_height,
):
    for combo in combos:
        if combo.layers is not None and layer_index not in combo.layers:
            continue

        points = []
        for position in combo.positions:
            if position < 0 or position >= len(keys):
                continue
            points.append(
                transform_key_center(
                    keys[position],
                    min_x,
                    min_y,
                    key_unit_px,
                    padding,
                    padding + header_height,
                )
            )
        if len(points) < 2:
            continue

        point_attr = " ".join(f"{px(x)},{px(y)}" for x, y in points)
        label_x = sum(x for x, _ in points) / len(points)
        label_y = min(y for _, y in points) - 13
        label = html.escape(combo_label(combo))
        label_width = max(30, len(label) * 6.2 + 14)
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", combo.name)
        lines.append(f'<g class="combo combo-{safe_name}">')
        lines.append(f'<polyline points="{point_attr}"/>')
        for x, y in points:
            lines.append(f'<circle class="combo-dot" cx="{px(x)}" cy="{px(y)}" r="3.2"/>')
        lines.append(
            f'<rect class="combo-label-bg" x="{px(label_x - label_width / 2)}" y="{px(label_y - 8)}" width="{px(label_width)}" height="16" rx="8" ry="8"/>'
        )
        lines.append(
            f'<text class="combo-label" x="{px(label_x)}" y="{px(label_y)}">{label}</text>'
        )
        lines.append("</g>")


def render_svg(keys, modules, combos, title, output_path, key_unit_px, padding, show_row_col, layers):
    min_x, min_y, max_x, max_y = layout_bounds(keys, modules)
    header_height = 34
    layout_width = (max_x - min_x) * key_unit_px + padding * 2
    layout_height = (max_y - min_y) * key_unit_px + padding * 2 + header_height
    layer_gap = 42
    rendered_layers = layers or [Layer("physical_layout", title, [])]
    width = layout_width
    height = layout_height * len(rendered_layers) + layer_gap * (len(rendered_layers) - 1)

    lines = [
        f'<svg width="{px(width)}" height="{px(height)}" viewBox="0 0 {px(width)} {px(height)}" class="physical-layout" xmlns="http://www.w3.org/2000/svg">',
        "<style>",
        "svg.physical-layout { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; background: #f8faf7; color: #1d2520; }",
        ".key rect { fill: #ffffff; stroke: #8a958d; stroke-width: 1.25; }",
        ".key text { text-anchor: middle; dominant-baseline: middle; fill: #1d2520; }",
        ".key .tap { font-size: 11px; font-weight: 700; }",
        ".key .hold, .key .matrix { font-size: 7.5px; fill: #69736c; }",
        ".key.transparent rect { fill: #f3f5f2; stroke-dasharray: 4 3; }",
        ".key.transparent text { fill: #9aa39d; }",
        ".key.none rect { fill: #ecefed; }",
        ".module rect, .module circle { fill: #e8f1f2; stroke: #527a82; stroke-width: 1.25; stroke-dasharray: 5 3; }",
        ".module-trackball circle, .module-rotary-encoder circle { fill: #edf4e8; stroke: #6e8a52; stroke-dasharray: none; }",
        ".module text { text-anchor: middle; dominant-baseline: middle; fill: #24434a; }",
        ".module .module-label { font-size: 10px; font-weight: 700; }",
        ".module .module-type { font-size: 7.5px; fill: #527a82; }",
        ".combo polyline { fill: none; stroke: #d46f2c; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; opacity: 0.92; }",
        ".combo .combo-dot { fill: #d46f2c; stroke: #ffffff; stroke-width: 1.2; }",
        ".combo .combo-label-bg { fill: #fff4df; stroke: #d46f2c; stroke-width: 1.1; }",
        ".combo .combo-label { font-size: 9px; font-weight: 700; text-anchor: middle; dominant-baseline: middle; fill: #6f330f; }",
        ".title { font-size: 16px; font-weight: 700; text-anchor: start; dominant-baseline: hanging; fill: #1d2520; }",
        ".subtitle { font-size: 10px; fill: #69736c; text-anchor: start; dominant-baseline: hanging; }",
        ".origin { fill: #d1495b; opacity: 0.75; }",
        "</style>",
        f'<title>{html.escape(title)}</title>',
    ]

    for layer_index, layer in enumerate(rendered_layers):
        y_offset = layer_index * (layout_height + layer_gap)
        lines.append(f'<g class="layer layer-{html.escape(layer.name)}" transform="translate(0 {px(y_offset)})">')
        lines.append(
            f'<text class="title" x="{px(padding)}" y="{px(padding / 3)}">{html.escape(layer.label)}</text>'
        )
        if layer.bindings:
            lines.append(
                f'<text class="subtitle" x="{px(padding)}" y="{px(padding / 3 + 18)}">{len(layer.bindings)} bindings</text>'
            )
        render_modules(lines, modules, min_x, min_y, key_unit_px, padding, header_height)
        for index, key in enumerate(keys):
            x, y, rx, ry = transform_key(key, min_x, min_y, key_unit_px, padding, padding + header_height)
            key_width = key.width * key_unit_px
            key_height = key.height * key_unit_px
            group_transform = (
                f'translate({px(x)} {px(y)}) rotate({px(key.rotation)} {px(rx - x)} {px(ry - y)})'
            )
            binding = layer.bindings[index] if index < len(layer.bindings) else None
            css_class = binding.css_class if binding else ""
            matrix_label = f"r{key.row} c{key.col}" if key.row is not None and key.col is not None else ""
            lines.extend(
                [
                    f'<g class="key keypos-{index} {css_class}" transform="{group_transform}">',
                    f'<rect x="0" y="0" width="{px(key_width)}" height="{px(key_height)}" rx="6" ry="6"/>',
                ]
            )
            if binding:
                lines.extend(render_key_text(binding, key_width, key_height))
            else:
                lines.append(
                    f'<text class="tap" x="{px(key_width / 2)}" y="{px(key_height / 2 - (6 if show_row_col and matrix_label else 0))}">{index}</text>'
                )
            if show_row_col and matrix_label and not binding:
                lines.append(
                    f'<text class="matrix" x="{px(key_width / 2)}" y="{px(key_height / 2 + 10)}">{matrix_label}</text>'
                )
            lines.append("</g>")
            if key.rotation and not layer.bindings:
                lines.append(f'<circle class="origin" cx="{px(rx)}" cy="{px(ry)}" r="2.5"/>')
        render_combos(
            lines,
            combos,
            keys,
            layer_index,
            min_x,
            min_y,
            key_unit_px,
            padding,
            header_height,
        )
        lines.append("</g>")

    lines.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")


def generate(input_path, output_path, layout_name, keymap_path, key_unit_px, padding, show_row_col):
    text = read_devicetree_with_includes(input_path)
    layout_label = layout_name
    if layout_label and try_find_labeled_block(text, layout_label) is None:
        layout_label = None
    layout_label = layout_label or find_first_physical_layout_label(text)
    layout_block = find_labeled_block(text, layout_label)
    keys = parse_key_attrs(layout_block)
    modules = parse_modules(text)
    apply_positions(keys, parse_transform_positions(text, layout_block))
    title = parse_display_name(layout_block, layout_label)
    layers = parse_keymap_layers(keymap_path) if keymap_path else []
    combos = parse_keymap_combos(keymap_path) if keymap_path else []

    for layer in layers:
        if len(layer.bindings) != len(keys):
            print(
                f"Warning: layer {layer.label} binding count ({len(layer.bindings)}) does not match key count ({len(keys)}); labels will be partial."
            )

    render_svg(keys, modules, combos, title, output_path, key_unit_px, padding, show_row_col, layers)


def main():
    parser = argparse.ArgumentParser(
        description="Generate an SVG preview from a ZMK zmk,physical-layout node and optional .keymap."
    )
    parser.add_argument("input", type=Path, help="ZMK .dtsi/.overlay containing zmk,physical-layout")
    parser.add_argument("output", type=Path, help="SVG file to write")
    parser.add_argument("--keymap", type=Path, help="ZMK .keymap file to draw on top of the physical layout")
    parser.add_argument("--layout", help="Physical layout node label, e.g. layout_SAA")
    parser.add_argument("--key-unit-px", type=float, default=52, help="Pixel size for a 1u key")
    parser.add_argument("--padding", type=float, default=30, help="SVG padding in pixels")
    parser.add_argument("--no-row-col", action="store_true", help="Hide matrix row/column labels")
    args = parser.parse_args()

    generate(
        args.input,
        args.output,
        args.layout,
        args.keymap,
        args.key_unit_px,
        args.padding,
        not args.no_row_col,
    )


if __name__ == "__main__":
    main()

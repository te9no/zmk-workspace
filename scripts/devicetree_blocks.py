"""Small comment/string-aware Devicetree block scanner."""

from __future__ import annotations

import re


def code_mask(text: str) -> str:
    """Return text-shaped code with comments and string contents blanked."""
    chars = list(text)
    state = "code"
    index = 0
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if current == '"':
                chars[index] = " "
                state = "string"
            elif current == "/" and following == "/":
                chars[index] = chars[index + 1] = " "
                state = "line_comment"
                index += 1
            elif current == "/" and following == "*":
                chars[index] = chars[index + 1] = " "
                state = "block_comment"
                index += 1
        elif state == "string":
            chars[index] = "\n" if current == "\n" else " "
            if current == "\\" and following:
                chars[index + 1] = " "
                index += 1
            elif current == '"':
                state = "code"
        elif state == "line_comment":
            chars[index] = "\n" if current == "\n" else " "
            if current == "\n":
                state = "code"
        else:
            chars[index] = "\n" if current == "\n" else " "
            if current == "*" and following == "/":
                chars[index + 1] = " "
                state = "code"
                index += 1
        index += 1
    return "".join(chars)


def block_end(mask: str, start: int, description: str) -> int:
    depth = 1
    index = start
    while index < len(mask) and depth:
        if mask[index] == "{":
            depth += 1
        elif mask[index] == "}":
            depth -= 1
        index += 1
    if depth:
        raise SystemExit(f"Unclosed node block for {description}")
    return index


def find_labeled_block(text: str, label: str) -> str:
    mask = code_mask(text)
    match = re.search(rf"\b{re.escape(label)}\s*:\s*[A-Za-z0-9_,@-]+\s*\{{", mask)
    if not match:
        raise SystemExit(f"Could not find node label: {label}")
    end = block_end(mask, match.end(), f"label: {label}")
    return text[match.end(): end - 1]


def find_named_block(text: str, name: str) -> str:
    mask = code_mask(text)
    match = re.search(rf"\b{re.escape(name)}\s*\{{", mask)
    if not match:
        raise SystemExit(f"Could not find node: {name}")
    end = block_end(mask, match.end(), f"node: {name}")
    return text[match.end(): end - 1]


def iter_blocks(text: str, pattern: re.Pattern):
    mask = code_mask(text)
    index = 0
    while match := pattern.search(mask, index):
        end = block_end(mask, match.end(), f"node: {match.group(1)}")
        yield match.group(1), text[match.end(): end - 1]
        index = end

"""Markdown message formatting for DingTalk replies."""

from __future__ import annotations

from collections.abc import Iterable


Field = tuple[str, object]


def build_markdown_message(
    title: str,
    fields: Iterable[Field],
    summary: str | None = None,
    body_lines: Iterable[str] | None = None,
) -> str:
    lines = [f"### {title}", ""]
    for label, value in fields:
        normalized_value = str(value or "").strip() or "-"
        lines.append(f"- **{label}**：{normalized_value}")

    if summary:
        lines.extend(["", "> 摘要"])
        for line in str(summary).splitlines():
            lines.append(f"> {line}")

    if body_lines:
        lines.append("")
        lines.extend(str(line) for line in body_lines)

    return "\n".join(lines)

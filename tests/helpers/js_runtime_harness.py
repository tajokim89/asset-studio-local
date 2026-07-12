from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def _lexical_mask(source: str) -> str:
    """Blank JS comments and literals while preserving source offsets."""
    chars = list(source)
    mask = list(source)
    index = 0
    previous = None
    regex_after = set("([{=,:;!&|?+-*%^~<>")

    def blank(start: int, end: int) -> None:
        for position in range(start, end):
            if chars[position] != "\n":
                mask[position] = " "

    while index < len(chars):
        char = chars[index]
        if char.isspace():
            index += 1
            continue
        if char == "/" and index + 1 < len(chars) and chars[index + 1] in "/*":
            start = index
            if chars[index + 1] == "/":
                index += 2
                while index < len(chars) and chars[index] != "\n":
                    index += 1
            else:
                index += 2
                while index + 1 < len(chars) and chars[index:index + 2] != ["*", "/"]:
                    index += 1
                index = min(index + 2, len(chars))
            blank(start, index)
            continue
        if char in "'\"`":
            start, delimiter = index, char
            index += 1
            while index < len(chars):
                if chars[index] == "\\":
                    index += 2
                elif chars[index] == delimiter:
                    index += 1
                    break
                else:
                    index += 1
            blank(start, min(index, len(chars)))
            previous = "literal"
            continue
        if char == "/" and (
            previous is None
            or previous in regex_after
            or previous in {"return", "case", "throw", "=>"}
        ):
            start = index
            index += 1
            in_class = False
            while index < len(chars):
                if chars[index] == "\\":
                    index += 2
                elif chars[index] == "[":
                    in_class = True
                    index += 1
                elif chars[index] == "]":
                    in_class = False
                    index += 1
                elif chars[index] == "/" and not in_class:
                    index += 1
                    while index < len(chars) and chars[index].isalpha():
                        index += 1
                    break
                else:
                    index += 1
            blank(start, min(index, len(chars)))
            previous = "literal"
            continue
        if char.isalpha() or char in "_$":
            start = index
            while index < len(chars) and (chars[index].isalnum() or chars[index] in "_$"):
                index += 1
            previous = source[start:index]
        else:
            previous = "=>" if source[index:index + 2] == "=>" else char
            index += 2 if previous == "=>" else 1
    return "".join(mask)


class JavaScriptRuntimeHarness:
    def __init__(self, source_path: Path):
        self.source_path = Path(source_path)
        self.source = self.source_path.read_text(encoding="utf-8")
        self.mask = _lexical_mask(self.source)

    def source_for(self, name: str) -> str:
        function = re.search(
            rf"\b(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{",
            self.mask,
        )
        if function is not None:
            opening = function.end() - 1
            depth = 0
            for index in range(opening, len(self.mask)):
                if self.mask[index] == "{":
                    depth += 1
                elif self.mask[index] == "}":
                    depth -= 1
                    if depth == 0:
                        return self.source[function.start():index + 1]
            raise AssertionError(f"Unclosed production function: {name}")

        declaration = re.search(
            rf"\b(?:const|let|var)\s+{re.escape(name)}\s*=",
            self.mask,
        )
        if declaration is not None:
            depths = {"(": 0, "[": 0, "{": 0}
            closing = {")": "(", "]": "[", "}": "{"}
            for index in range(declaration.end(), len(self.mask)):
                char = self.mask[index]
                if char in depths:
                    depths[char] += 1
                elif char in closing:
                    depths[closing[char]] -= 1
                elif char == ";" and not any(depths.values()):
                    return self.source[declaration.start():index + 1]
            raise AssertionError(f"Unclosed production declaration: {name}")

        raise AssertionError(f"Production symbol not found: {name}")

    def run_json(
        self,
        *,
        names: tuple[str, ...],
        script: str,
        prelude: str = "",
    ):
        production = "\n\n".join(self.source_for(name) for name in names)
        source = "\n\n".join(part for part in (prelude, production, script) if part)
        completed = subprocess.run(
            ["node", "-e", source],
            cwd=self.source_path.parents[1],
            text=True,
            capture_output=True,
            timeout=15,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"Node runtime failed ({completed.returncode})\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise AssertionError(
                f"Node runtime emitted invalid JSON: {error}\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            ) from error

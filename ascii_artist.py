# ascii_artist.py
# __all__: 8

__all__ = [
    "generate_square",
    "generate_triangle",
    "generate_diamond",
    "get_template",
    "list_templates",
    "render_prompt_ascii",
    "SUPPORTED",
    "UNSUPPORTED",
]

import re
from typing import Any, Callable, Protocol

SUPPORTED = {
    "generation": [
        "square / triangle / diamond text-art generation",
        "non-empty single-line string tokens, including Unicode",
        "built-in text-art templates",
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
        "fuzzy removal of arbitrary prose around generated art",
    ],
    "integration": [
        "direct dependency on a specific LLM SDK",
        "repository-local runtime assets or configuration files",
    ],
}

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

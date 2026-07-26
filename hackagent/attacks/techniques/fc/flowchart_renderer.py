# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Flowchart image renderer for FC-Attack.

Generates flowchart images from step descriptions using Graphviz DOT format.
Supports three layout modes: vertical, horizontal, and tortuous (S-shaped).

Based on: Zhang et al., "FC-Attack: Jailbreaking Multimodal Large
Language Models via Auto-Generated Flowcharts" (EMNLP 2025 Findings)
"""

import base64
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
import textwrap
import zipfile
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_GRAPHVIZ_AVAILABLE: bool | None = None
_GRAPHVIZ_DOT_BIN: str | None = None

_GRAPHVIZ_LATEST_RELEASE_API = (
    "https://gitlab.com/api/v4/projects/4207231/releases/permalink/latest"
)


def _env_truthy(value: str | None, *, default: bool = True) -> bool:
    """Interpret boolean-ish environment variables."""
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _hackagent_data_dir() -> Path:
    """Return the OS-specific persistent HackAgent data directory."""
    system = platform.system().lower()

    if system == "windows":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return (Path(base) / "hackagent").resolve()
        return (Path.home() / "AppData" / "Local" / "hackagent").resolve()

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return (Path(xdg_data_home).expanduser().resolve() / "hackagent").resolve()
    return (Path.home() / ".local" / "share" / "hackagent").resolve()


def _graphviz_storage_dir() -> Path:
    """Return the persistent directory used for Graphviz portable binaries."""
    return _hackagent_data_dir() / "graphviz"


def _is_executable_file(path: Path) -> bool:
    """Return True when *path* points to an executable file."""
    return path.is_file() and os.access(path, os.X_OK)


def _find_dot_binary(root: Path) -> Path | None:
    """Locate the ``dot`` binary under a directory tree."""
    if not root.exists():
        return None

    pattern = "dot.exe" if platform.system().lower() == "windows" else "dot"
    candidates: List[Path] = []
    for path in root.rglob(pattern):
        if path.is_file():
            candidates.append(path)

    if not candidates:
        return None

    def _candidate_rank(path: Path) -> tuple[int, int]:
        parts_lower = {part.lower() for part in path.parts}
        has_bin = 0 if "bin" in parts_lower else 1
        return (has_bin, len(path.parts))

    candidates.sort(key=_candidate_rank)
    return candidates[0]


def _pick_latest_graphviz_asset(
    links: List[Dict[str, Any]],
    system_name: str,
) -> Dict[str, str] | None:
    """Choose the best Graphviz archive for the current OS from release links."""
    os_name = system_name.lower()

    if os_name == "darwin":
        patterns = [
            r"^Darwin_.*_graphviz-.*-(arm64|x86_64)\.pkg$",
            r"^Darwin_.*_Graphviz-.*-Darwin\.zip$",
            r"Graphviz-.*-Darwin\.zip$",
        ]
    elif os_name == "windows":
        patterns = [
            r"^windows_.*_Release_Graphviz-.*-win64\.zip$",
            r"Graphviz-.*-win64\.zip$",
        ]
    else:
        return None

    for pattern in patterns:
        rx = re.compile(pattern)
        for link in links:
            name = str(link.get("name") or "")
            if not name or name.endswith(".sha256"):
                continue
            if not rx.search(name):
                continue
            url = str(link.get("direct_asset_url") or link.get("url") or "")
            if url:
                return {"name": name, "url": url}
    return None


def _fetch_graphviz_latest_release() -> Dict[str, Any]:
    """Fetch metadata for the latest Graphviz release from GitLab."""
    req = Request(
        _GRAPHVIZ_LATEST_RELEASE_API,
        headers={"User-Agent": "hackagent-graphviz-bootstrap/1.0"},
    )
    with urlopen(req, timeout=20) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _download_file(url: str, destination: Path) -> None:
    """Download *url* to *destination* using streaming IO."""
    req = Request(url, headers={"User-Agent": "hackagent-graphviz-bootstrap/1.0"})
    with urlopen(req, timeout=60) as response, open(destination, "wb") as out:
        shutil.copyfileobj(response, out)


def _safe_join(base_dir: Path, relative_path: str) -> Path:
    """Safely join a ZIP member path to *base_dir* (zip-slip protection)."""
    base_resolved = base_dir.resolve()
    candidate = (base_dir / relative_path).resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise ValueError(f"Unsafe archive entry path: {relative_path}")
    return candidate


def _extract_zip_preserving_symlinks(zip_path: Path, destination: Path) -> None:
    """Extract ZIP preserving Unix symlinks when present in archive metadata."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            out_path = _safe_join(destination, info.filename)

            if info.is_dir():
                out_path.mkdir(parents=True, exist_ok=True)
                continue

            out_path.parent.mkdir(parents=True, exist_ok=True)

            mode = (info.external_attr >> 16) & 0xFFFF
            is_symlink = stat.S_ISLNK(mode)

            if is_symlink:
                link_target = zf.read(info).decode("utf-8").strip()
                if out_path.exists() or out_path.is_symlink():
                    out_path.unlink()
                try:
                    os.symlink(link_target, out_path)
                except OSError:
                    # Fallback: keep the placeholder file if symlink creation fails.
                    out_path.write_text(link_target, encoding="utf-8")
                continue

            with zf.open(info, "r") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            if mode:
                try:
                    out_path.chmod(mode)
                except OSError:
                    logger.debug("Could not chmod extracted file %s", out_path)


def _repair_macos_dylib_symlinks(root: Path) -> int:
    """Repair dylib alias files extracted as plain text instead of symlinks."""
    if platform.system().lower() != "darwin" or not root.exists():
        return 0

    repaired = 0
    for alias_file in root.rglob("*.dylib"):
        if alias_file.is_symlink() or not alias_file.is_file():
            continue

        try:
            size = alias_file.stat().st_size
        except OSError:
            continue

        # Symlink placeholders from zip extraction are tiny text files.
        if size == 0 or size > 256:
            continue

        try:
            target_name = alias_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            continue

        if not target_name or "/" in target_name or "\\" in target_name:
            continue
        if not target_name.endswith(".dylib"):
            continue

        target_path = alias_file.parent / target_name
        if not target_path.exists() or target_path == alias_file:
            continue

        try:
            alias_file.unlink()
            os.symlink(target_name, alias_file)
            repaired += 1
        except OSError:
            logger.debug("Could not repair dylib symlink for %s", alias_file)

    if repaired:
        logger.info("Repaired %d Graphviz dylib symlink(s) under %s", repaired, root)
    return repaired


def _extract_macos_pkg_payload(pkg_path: Path, destination: Path) -> None:
    """Extract Graphviz macOS .pkg payload into *destination* without system install."""
    expanded_dir = destination / "_pkg_expanded"
    if expanded_dir.exists():
        shutil.rmtree(expanded_dir)

    result = subprocess.run(
        ["pkgutil", "--expand-full", str(pkg_path), str(expanded_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "pkgutil failed while extracting Graphviz package: "
            f"{(result.stderr or result.stdout).strip()[:300]}"
        )

    payload_candidates = list(expanded_dir.rglob("Payload/bin/dot"))
    if not payload_candidates:
        raise RuntimeError("Could not locate Graphviz dot binary inside macOS pkg")

    payload_root = payload_candidates[0].parent.parent
    shutil.copytree(payload_root, destination, dirs_exist_ok=True, symlinks=True)

    shutil.rmtree(expanded_dir, ignore_errors=True)


def _build_graphviz_runtime_env(dot_binary: str) -> Dict[str, str]:
    """Build environment variables required to run a local Graphviz binary."""
    env = os.environ.copy()
    dot_path = Path(dot_binary).expanduser().resolve()

    bin_dir = str(dot_path.parent)
    env["PATH"] = (
        f"{bin_dir}{os.pathsep}{env.get('PATH', '')}" if env.get("PATH") else bin_dir
    )

    lib_candidates = [
        dot_path.parent.parent / "lib",
        dot_path.parent.parent / "lib" / "graphviz",
    ]
    lib_dirs = [str(p) for p in lib_candidates if p.exists() and p.is_dir()]

    if lib_dirs:
        lib_prefix = os.pathsep.join(lib_dirs)
        system = platform.system().lower()
        if system == "darwin":
            env["DYLD_LIBRARY_PATH"] = (
                f"{lib_prefix}{os.pathsep}{env.get('DYLD_LIBRARY_PATH', '')}"
                if env.get("DYLD_LIBRARY_PATH")
                else lib_prefix
            )
            env["DYLD_FALLBACK_LIBRARY_PATH"] = (
                f"{lib_prefix}{os.pathsep}{env.get('DYLD_FALLBACK_LIBRARY_PATH', '')}"
                if env.get("DYLD_FALLBACK_LIBRARY_PATH")
                else lib_prefix
            )
        elif system == "linux":
            env["LD_LIBRARY_PATH"] = (
                f"{lib_prefix}{os.pathsep}{env.get('LD_LIBRARY_PATH', '')}"
                if env.get("LD_LIBRARY_PATH")
                else lib_prefix
            )

    return env


def _patch_macos_install_names(bundle_root: Path) -> None:
    """Patch macOS Graphviz binaries to use local bundle library paths."""
    if platform.system().lower() != "darwin":
        return

    lib_root = bundle_root / "lib"
    if not lib_root.exists():
        return

    old_prefixes = (
        "/usr/local/graphviz/lib/",
        "/opt/homebrew/opt/libtool/lib/",
    )

    candidates: List[Path] = []
    candidates.extend([p for p in (bundle_root / "bin").glob("*") if p.is_file()])
    candidates.extend([p for p in lib_root.glob("*.dylib") if p.is_file()])
    candidates.extend(
        [p for p in (lib_root / "graphviz").glob("*.dylib") if p.is_file()]
    )

    for file_path in candidates:
        try:
            out = subprocess.run(
                ["otool", "-L", str(file_path)],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            continue
        if out.returncode != 0:
            continue

        dep_lines = [line.strip() for line in out.stdout.splitlines()[1:]]
        for line in dep_lines:
            dep = line.split(" ", 1)[0].strip()
            replacement: Path | None = None
            for prefix in old_prefixes:
                if dep.startswith(prefix):
                    replacement = lib_root / dep.split(prefix, 1)[1]
                    break

            if not replacement or not replacement.exists():
                continue

            if str(replacement) == dep:
                continue

            subprocess.run(
                [
                    "install_name_tool",
                    "-change",
                    dep,
                    str(replacement),
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )

        if file_path.suffix == ".dylib":
            id_out = subprocess.run(
                ["otool", "-D", str(file_path)],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if id_out.returncode != 0:
                continue
            ids = [
                line.strip() for line in id_out.stdout.splitlines()[1:] if line.strip()
            ]
            if not ids:
                continue

            old_id = ids[0]
            new_id: Path | None = None
            for prefix in old_prefixes:
                if old_id.startswith(prefix):
                    candidate = lib_root / old_id.split(prefix, 1)[1]
                    if candidate.exists():
                        new_id = candidate
                    break

            if not new_id or str(new_id) == old_id:
                continue

            subprocess.run(
                ["install_name_tool", "-id", str(new_id), str(file_path)],
                capture_output=True,
                text=True,
                timeout=20,
            )


def _initialize_graphviz_plugins(dot_binary: str) -> None:
    """Run ``dot -c`` to generate/refresh plugin configuration for local bundles."""
    dot_path = Path(dot_binary).expanduser().resolve()
    try:
        storage_root = _graphviz_storage_dir().resolve()
        dot_path.relative_to(storage_root)
    except Exception:
        return

    env = _build_graphviz_runtime_env(dot_binary)
    subprocess.run(
        [dot_binary, "-c"],
        capture_output=True,
        text=True,
        timeout=40,
        env=env,
    )


def _resolve_dot_binary(allow_download: bool | None = None) -> str | None:
    """Resolve a usable Graphviz ``dot`` binary path.

    Args:
        allow_download: Controls whether portable binary download is allowed.
            - ``True``: explicitly allow download fallback.
            - ``False``: disable download fallback.
            - ``None``: follow ``HACKAGENT_GRAPHVIZ_AUTO_DOWNLOAD`` (default).
    """
    global _GRAPHVIZ_DOT_BIN
    if _GRAPHVIZ_DOT_BIN:
        return _GRAPHVIZ_DOT_BIN

    dot_from_env = os.getenv("HACKAGENT_GRAPHVIZ_DOT")
    if dot_from_env:
        path = Path(dot_from_env).expanduser().resolve()
        if path.exists() and (
            platform.system().lower() == "windows" or _is_executable_file(path)
        ):
            _GRAPHVIZ_DOT_BIN = str(path)
            return _GRAPHVIZ_DOT_BIN
        logger.warning(
            "Ignoring HACKAGENT_GRAPHVIZ_DOT=%s (file not found or not executable)",
            dot_from_env,
        )

    dot_on_path = shutil.which("dot")
    if dot_on_path:
        _GRAPHVIZ_DOT_BIN = dot_on_path
        return _GRAPHVIZ_DOT_BIN

    if allow_download is None:
        should_download = _env_truthy(
            os.getenv("HACKAGENT_GRAPHVIZ_AUTO_DOWNLOAD"), default=True
        )
    else:
        should_download = allow_download

    if not should_download:
        return None

    try:
        release = _fetch_graphviz_latest_release()
        links = release.get("assets", {}).get("links", [])
        if not isinstance(links, list):
            logger.warning("Invalid Graphviz release payload: missing assets.links")
            return None

        asset = _pick_latest_graphviz_asset(links, platform.system())
        if not asset:
            logger.warning(
                "No portable Graphviz archive found for OS '%s'. "
                "Set HACKAGENT_GRAPHVIZ_DOT to a local dot binary.",
                platform.system(),
            )
            return None

        version = str(release.get("tag_name") or "latest")
        asset_name = asset["name"]
        asset_url = asset["url"]
        install_root = _graphviz_storage_dir() / version / Path(asset_name).stem
        install_root.mkdir(parents=True, exist_ok=True)

        _repair_macos_dylib_symlinks(install_root)

        existing = _find_dot_binary(install_root)
        if existing:
            _patch_macos_install_names(install_root)
            _initialize_graphviz_plugins(str(existing))
            _GRAPHVIZ_DOT_BIN = str(existing)
            return _GRAPHVIZ_DOT_BIN

        archive_path = install_root / asset_name
        logger.info("Downloading Graphviz archive: %s", asset_name)
        _download_file(asset_url, archive_path)

        archive_name = archive_path.name.lower()
        if archive_name.endswith(".zip"):
            _extract_zip_preserving_symlinks(archive_path, install_root)
        elif archive_name.endswith(".pkg") and platform.system().lower() == "darwin":
            _extract_macos_pkg_payload(archive_path, install_root)
        else:
            logger.warning(
                "Unsupported Graphviz archive type '%s'",
                archive_path.name,
            )
            return None

        _repair_macos_dylib_symlinks(install_root)
        _patch_macos_install_names(install_root)

        extracted_dot = _find_dot_binary(install_root)
        if not extracted_dot:
            logger.warning(
                "Graphviz archive extracted but dot binary was not found in %s",
                install_root,
            )
            return None

        if platform.system().lower() != "windows":
            try:
                current_mode = extracted_dot.stat().st_mode
                extracted_dot.chmod(current_mode | 0o111)
            except OSError:
                logger.debug("Could not chmod +x %s", extracted_dot, exc_info=True)

            _initialize_graphviz_plugins(str(extracted_dot))

        _GRAPHVIZ_DOT_BIN = str(extracted_dot)
        return _GRAPHVIZ_DOT_BIN
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        logger.warning("Graphviz auto-download failed: %s", exc)
        return None


def _check_graphviz() -> bool:
    """Check if the ``dot`` binary is available on the system."""
    global _GRAPHVIZ_AVAILABLE
    if _GRAPHVIZ_AVAILABLE is None:
        _GRAPHVIZ_AVAILABLE = _resolve_dot_binary() is not None
    return _GRAPHVIZ_AVAILABLE


def ensure_graphviz_dot_available(allow_download: bool | None = None) -> str | None:
    """Ensure Graphviz ``dot`` is available and return its resolved path.

    This function is safe to call during setup flows (e.g. ``hackagent init``).
    It may trigger automatic local binary download when enabled.

    Args:
        allow_download: See ``_resolve_dot_binary``.
    """
    global _GRAPHVIZ_AVAILABLE
    dot_binary = _resolve_dot_binary(allow_download=allow_download)
    _GRAPHVIZ_AVAILABLE = dot_binary is not None
    return dot_binary


# ─── DOT text helpers ─────────────────────────────────────────────────────────


def _escape_dot(text: str) -> str:
    """Escape special characters for DOT label strings."""
    text = text.replace("\\", "\\\\")
    text = text.replace('"', "'")
    text = text.replace("\n", " ")
    # Strip markdown artifacts
    text = text.replace("**", "").replace("*", "")
    return text


def _wrap_text(text: str, width: int = 30) -> str:
    """Wrap text with DOT newline delimiters."""
    escaped = _escape_dot(text)
    return "\\n".join(textwrap.wrap(escaped, width=width))


# ─── Text format serializers ─────────────────────────────────────────────────


def _escape_mermaid(text: str) -> str:
    """Escape text for Mermaid node labels."""
    return text.replace('"', "'").replace("\n", " ")


def _escape_tikz(text: str) -> str:
    """Escape text for TikZ/LaTeX labels."""
    for ch in ("&", "%", "$", "#", "_", "{", "}"):
        text = text.replace(ch, f"\\{ch}")
    text = text.replace("~", r"\textasciitilde{}")
    text = text.replace("\n", " ")
    return text


def _escape_plantuml(text: str) -> str:
    """Escape text for PlantUML labels."""
    return text.replace("\n", " ").replace(";", ",")


def steps_to_mermaid(goal_text: str, steps: List[str], layout: str = "vertical") -> str:
    """Serialize steps as a Mermaid flowchart respecting layout direction."""
    if layout == "horizontal":
        return _mermaid_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _mermaid_tortuous(goal_text, steps)
    return _mermaid_vertical(goal_text, steps)


def _mermaid_vertical(goal_text: str, steps: List[str]) -> str:
    """Vertical (top-down) Mermaid flowchart."""
    lines = ["flowchart TD"]
    lines.append(f'    goal(("{_escape_mermaid(goal_text)}"))')
    for i, step in enumerate(steps, 1):
        lines.append(f'    step{i}["{_escape_mermaid(f"{i}. {step}")}"]')
    lines.append("    goal --> step1")
    for i in range(1, len(steps)):
        lines.append(f"    step{i} --> step{i + 1}")
    return "\n".join(lines)


def _mermaid_horizontal(goal_text: str, steps: List[str]) -> str:
    """Horizontal (left-to-right) Mermaid flowchart."""
    lines = ["flowchart LR"]
    lines.append(f'    goal(("{_escape_mermaid(goal_text)}"))')
    for i, step in enumerate(steps, 1):
        lines.append(f'    step{i}["{_escape_mermaid(f"{i}. {step}")}"]')
    lines.append("    goal --> step1")
    for i in range(1, len(steps)):
        lines.append(f"    step{i} --> step{i + 1}")
    return "\n".join(lines)


def _mermaid_tortuous(goal_text: str, steps: List[str], cols: int = 3) -> str:
    """Tortuous (S-shaped) Mermaid block diagram using block-beta with columns."""
    all_ids = ["goal"] + [f"step{i}" for i in range(1, len(steps) + 1)]
    all_labels = [_escape_mermaid(goal_text)] + [
        _escape_mermaid(f"{i}. {s}") for i, s in enumerate(steps, 1)
    ]

    # Split into rows
    rows = [all_ids[i : i + cols] for i in range(0, len(all_ids), cols)]
    label_map = dict(zip(all_ids, all_labels))

    # Use (2*cols - 1) columns to insert space blocks between nodes
    num_cols = 2 * cols - 1
    lines = ["block-beta", f"    columns {num_cols}"]

    # Place blocks row by row, reversing odd rows for S-shape
    for row_idx, row in enumerate(rows):
        is_reversed = row_idx % 2 == 1
        ordered = list(reversed(row)) if is_reversed else row
        # Pad row if shorter than cols (last row)
        for i, nid in enumerate(ordered):
            if i > 0:
                lines.append("    space")
            if nid == "goal":
                lines.append(f'    {nid}(("{label_map[nid]}"))')
            else:
                lines.append(f'    {nid}["{label_map[nid]}"]')
        # Fill remaining columns with space if row is short
        remaining = cols - len(ordered)
        for _ in range(remaining):
            lines.append("    space")
            lines.append("    space")
        # Empty spacer row between rows
        if row_idx < len(rows) - 1:
            for _ in range(num_cols):
                lines.append("    space")

    # Add edges in logical order
    lines.append("")
    for i in range(len(all_ids) - 1):
        lines.append(f"    {all_ids[i]} --> {all_ids[i + 1]}")

    return "\n".join(lines)


def steps_to_tikz(goal_text: str, steps: List[str], layout: str = "vertical") -> str:
    """Serialize steps as a TikZ flowchart (LaTeX) respecting layout direction."""
    if layout == "horizontal":
        return _tikz_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _tikz_tortuous(goal_text, steps)
    return _tikz_vertical(goal_text, steps)


def _tikz_vertical(goal_text: str, steps: List[str]) -> str:
    """Vertical (top-down) TikZ flowchart."""
    lines = [
        r"\begin{tikzpicture}[node distance=1.5cm, auto]",
        r"    \tikzstyle{goal} = [ellipse, draw, fill=blue!10, text width=5cm, text centered]",
        r"    \tikzstyle{step} = [rectangle, draw, fill=white, text width=5cm, text centered, rounded corners]",
        r"    \tikzstyle{arrow} = [thick, ->, >=stealth]",
        f"    \\node[goal] (goal) {{{_escape_tikz(goal_text)}}};",
    ]
    prev = "goal"
    for i, step in enumerate(steps, 1):
        lines.append(
            f"    \\node[step, below of={prev}] (s{i}) "
            f"{{{_escape_tikz(f'{i}. {step}')}}};"
        )
        lines.append(f"    \\draw[arrow] ({prev}) -- (s{i});")
        prev = f"s{i}"
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def _tikz_horizontal(goal_text: str, steps: List[str]) -> str:
    """Horizontal (left-to-right) TikZ flowchart."""
    lines = [
        r"\begin{tikzpicture}[node distance=6cm, auto]",
        r"    \tikzstyle{goal} = [ellipse, draw, fill=blue!10, text width=5cm, text centered]",
        r"    \tikzstyle{step} = [rectangle, draw, fill=white, text width=5cm, text centered, rounded corners]",
        r"    \tikzstyle{arrow} = [thick, ->, >=stealth]",
        f"    \\node[goal] (goal) {{{_escape_tikz(goal_text)}}};",
    ]
    prev = "goal"
    for i, step in enumerate(steps, 1):
        lines.append(
            f"    \\node[step, right of={prev}] (s{i}) "
            f"{{{_escape_tikz(f'{i}. {step}')}}};"
        )
        lines.append(f"    \\draw[arrow] ({prev}) -- (s{i});")
        prev = f"s{i}"
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def _tikz_tortuous(goal_text: str, steps: List[str], cols: int = 3) -> str:
    """Tortuous (S-shaped) TikZ flowchart with alternating row directions."""
    all_labels = [goal_text] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    all_ids = ["goal"] + [f"s{i}" for i in range(1, len(steps) + 1)]
    is_goal = [True] + [False] * len(steps)

    rows = [
        list(range(i, min(i + cols, len(all_ids))))
        for i in range(0, len(all_ids), cols)
    ]

    lines = [
        r"\begin{tikzpicture}[node distance=2cm and 5cm, auto]",
        r"    \tikzstyle{goal} = [ellipse, draw, fill=blue!10, text width=4cm, text centered]",
        r"    \tikzstyle{step} = [rectangle, draw, fill=white, text width=4cm, text centered, rounded corners]",
        r"    \tikzstyle{arrow} = [thick, ->, >=stealth]",
    ]

    # Place nodes row by row
    for row_idx, row in enumerate(rows):
        for col_idx, node_idx in enumerate(row):
            nid = all_ids[node_idx]
            label = _escape_tikz(all_labels[node_idx])
            style = "goal" if is_goal[node_idx] else "step"

            if row_idx == 0 and col_idx == 0:
                lines.append(f"    \\node[{style}] ({nid}) {{{label}}};")
            elif col_idx == 0:
                # First node in a new row: place below the last node of previous row
                # (right end for even→odd transition, left end for odd→even)
                prev_row = rows[row_idx - 1]
                anchor_idx = prev_row[-1] if (row_idx - 1) % 2 == 0 else prev_row[-1]
                lines.append(
                    f"    \\node[{style}, below of={all_ids[anchor_idx]}] ({nid}) {{{label}}};"
                )
            else:
                prev_in_row = all_ids[row[col_idx - 1]]
                # Even rows go left-to-right, odd rows right-to-left
                if row_idx % 2 == 0:
                    lines.append(
                        f"    \\node[{style}, right of={prev_in_row}] ({nid}) {{{label}}};"
                    )
                else:
                    lines.append(
                        f"    \\node[{style}, left of={prev_in_row}] ({nid}) {{{label}}};"
                    )

    # Draw edges sequentially
    for i in range(len(all_ids) - 1):
        lines.append(f"    \\draw[arrow] ({all_ids[i]}) -- ({all_ids[i + 1]});")

    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def steps_to_plantuml(
    goal_text: str, steps: List[str], layout: str = "vertical"
) -> str:
    """Serialize steps as a PlantUML flowchart respecting layout direction."""
    if layout == "horizontal":
        return _plantuml_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _plantuml_tortuous(goal_text, steps)
    return _plantuml_vertical(goal_text, steps)


def _plantuml_vertical(goal_text: str, steps: List[str]) -> str:
    """Vertical (top-down) PlantUML flowchart using directional arrows."""
    lines = ["@startuml"]
    # Define goal as ellipse and step nodes as rectangles
    lines.append(f'usecase "{_escape_plantuml(goal_text)}" as goal')
    for i, step in enumerate(steps, 1):
        lines.append(f'rectangle "{i}. {_escape_plantuml(step)}" as step{i}')
    # Connect with down arrows for vertical layout
    lines.append("goal -d-> step1")
    for i in range(1, len(steps)):
        lines.append(f"step{i} -d-> step{i + 1}")
    lines.append("@enduml")
    return "\n".join(lines)


def _plantuml_horizontal(goal_text: str, steps: List[str]) -> str:
    """Horizontal (left-to-right) PlantUML flowchart using directional arrows."""
    lines = ["@startuml"]
    # Define goal as ellipse and step nodes as rectangles
    lines.append(f'usecase "{_escape_plantuml(goal_text)}" as goal')
    for i, step in enumerate(steps, 1):
        lines.append(f'rectangle "{i}. {_escape_plantuml(step)}" as step{i}')
    # Connect with right arrows for horizontal layout
    lines.append("goal -r-> step1")
    for i in range(1, len(steps)):
        lines.append(f"step{i} -r-> step{i + 1}")
    lines.append("@enduml")
    return "\n".join(lines)


def _plantuml_tortuous(goal_text: str, steps: List[str], cols: int = 3) -> str:
    """Tortuous (S-shaped) PlantUML flowchart using directional arrows."""
    all_ids = ["goal"] + [f"step{i}" for i in range(1, len(steps) + 1)]
    all_labels = [_escape_plantuml(goal_text)] + [
        f"{i}. {_escape_plantuml(s)}" for i, s in enumerate(steps, 1)
    ]

    lines = ["@startuml"]
    # Define goal as ellipse, steps as rectangles
    lines.append(f'usecase "{all_labels[0]}" as goal')
    for nid, label in zip(all_ids[1:], all_labels[1:]):
        lines.append(f'rectangle "{label}" as {nid}')

    # Split into rows
    rows = [all_ids[i : i + cols] for i in range(0, len(all_ids), cols)]

    # Connect with directional arrows
    for row_idx, row in enumerate(rows):
        is_even = row_idx % 2 == 0
        # Horizontal edges within row
        for i in range(len(row) - 1):
            arrow = "-r->" if is_even else "-l->"
            lines.append(f"{row[i]} {arrow} {row[i + 1]}")
        # Vertical connector to next row (drop from end of current row)
        if row_idx < len(rows) - 1:
            src = row[-1]
            dst = rows[row_idx + 1][0]
            lines.append(f"{src} -d-> {dst}")

    lines.append("@enduml")
    return "\n".join(lines)


def steps_to_ascii(goal_text: str, steps: List[str], layout: str = "vertical") -> str:
    """Serialize steps as an ASCII art flowchart respecting layout direction."""
    if layout == "horizontal":
        return _ascii_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _ascii_tortuous(goal_text, steps)
    return _ascii_vertical(goal_text, steps)


def _ascii_vertical(goal_text: str, steps: List[str]) -> str:
    """Vertical ASCII flowchart (top-to-bottom)."""
    max_width = max(len(goal_text), *(len(f"{i}. {s}") for i, s in enumerate(steps, 1)))
    box_width = min(max_width + 4, 60)
    inner_width = box_width - 4

    def _box(text: str, is_goal: bool = False) -> List[str]:
        wrapped = textwrap.wrap(text, width=inner_width) or [text]
        if is_goal:
            border_top = "/" + "=" * (box_width - 2) + "\\"
            border_bot = "\\" + "=" * (box_width - 2) + "/"
        else:
            border_top = "+" + "-" * (box_width - 2) + "+"
            border_bot = "+" + "-" * (box_width - 2) + "+"
        box_lines = [border_top]
        for line in wrapped:
            box_lines.append(f"| {line:<{inner_width}} |")
        box_lines.append(border_bot)
        return box_lines

    result_lines: List[str] = []
    result_lines.extend(_box(goal_text, is_goal=True))
    for i, step in enumerate(steps, 1):
        arrow_padding = " " * (box_width // 2 - 1)
        result_lines.append(f"{arrow_padding}|")
        result_lines.append(f"{arrow_padding}v")
        result_lines.extend(_box(f"{i}. {step}"))

    return "\n".join(result_lines)


def _ascii_horizontal(goal_text: str, steps: List[str]) -> str:
    """Horizontal ASCII flowchart (left-to-right)."""
    all_items = [goal_text] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    box_width = 24
    inner_width = box_width - 4

    def _make_box_lines(text: str, is_goal: bool = False) -> List[str]:
        wrapped = textwrap.wrap(text, width=inner_width) or [text]
        if is_goal:
            border_top = "/" + "=" * (box_width - 2) + "\\"
            border_bot = "\\" + "=" * (box_width - 2) + "/"
        else:
            border_top = "+" + "-" * (box_width - 2) + "+"
            border_bot = "+" + "-" * (box_width - 2) + "+"
        box_lines = [border_top]
        for line in wrapped:
            box_lines.append(f"| {line:<{inner_width}} |")
        box_lines.append(border_bot)
        return box_lines

    # Build each box's lines
    boxes = [
        _make_box_lines(item, is_goal=(i == 0)) for i, item in enumerate(all_items)
    ]

    # Normalize heights
    max_height = max(len(b) for b in boxes)
    for b in boxes:
        while len(b) < max_height:
            b.insert(-1, f"| {'':<{inner_width}} |")

    # Combine horizontally with arrows at the middle row
    arrow_str = " --> "
    spacer_str = "     "
    mid_row = max_height // 2

    result_lines: List[str] = []
    for row_idx in range(max_height):
        parts = []
        for box_idx, box in enumerate(boxes):
            if box_idx > 0:
                parts.append(arrow_str if row_idx == mid_row else spacer_str)
            parts.append(box[row_idx])
        result_lines.append("".join(parts))

    return "\n".join(result_lines)


def _ascii_tortuous(goal_text: str, steps: List[str], cols: int = 3) -> str:
    """Tortuous (S-shaped/zigzag) ASCII flowchart."""
    all_items = [goal_text] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    box_width = 28
    inner_width = box_width - 4

    def _make_box(text: str, is_goal: bool = False) -> List[str]:
        wrapped = textwrap.wrap(text, width=inner_width) or [text]
        if is_goal:
            border_top = "/" + "=" * (box_width - 2) + "\\"
            border_bot = "\\" + "=" * (box_width - 2) + "/"
        else:
            border_top = "+" + "-" * (box_width - 2) + "+"
            border_bot = "+" + "-" * (box_width - 2) + "+"
        box_lines = [border_top]
        for line in wrapped:
            box_lines.append(f"| {line:<{inner_width}} |")
        box_lines.append(border_bot)
        return box_lines

    # Split items into rows
    rows: List[List[str]] = []
    for i in range(0, len(all_items), cols):
        rows.append(all_items[i : i + cols])

    result_lines: List[str] = []
    h_arrow = " --> "
    col_total_width = box_width + len(h_arrow)

    for row_idx, row_items in enumerate(rows):
        # Reverse odd rows for S-shape
        if row_idx % 2 == 1:
            row_items = list(reversed(row_items))

        # Build boxes for this row
        boxes = [
            _make_box(item, is_goal=(row_idx == 0 and i == 0))
            for i, item in enumerate(row_items)
        ]
        max_height = max(len(b) for b in boxes)
        for b in boxes:
            while len(b) < max_height:
                b.insert(-1, f"| {'':<{inner_width}} |")

        # Determine arrow direction for this row
        is_reversed = row_idx % 2 == 1
        arrow = " <-- " if is_reversed else " --> "

        # Render row horizontally
        for line_idx in range(max_height):
            parts = []
            for box_idx, box in enumerate(boxes):
                if box_idx > 0:
                    # Arrow in middle line
                    if line_idx == max_height // 2:
                        parts.append(arrow)
                    else:
                        parts.append(" " * len(arrow))
                parts.append(box[line_idx])
            result_lines.append("".join(parts))

        # Vertical connector to next row
        if row_idx < len(rows) - 1:
            # Position arrow at end of row (right side for even, left side for odd)
            if row_idx % 2 == 0:
                offset = (len(row_items) - 1) * col_total_width + box_width // 2
            else:
                offset = box_width // 2
            result_lines.append(" " * offset + "|")
            result_lines.append(" " * offset + "v")

    return "\n".join(result_lines)


def steps_to_dot(goal_text: str, steps: List[str], layout: str = "vertical") -> str:
    """Serialize steps as a Graphviz DOT source string respecting layout direction."""
    if layout == "horizontal":
        return _generate_dot_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _generate_dot_tortuous(goal_text, steps)
    return _generate_dot_vertical(goal_text, steps)


# Mapping of format names to serializer functions
TEXT_FORMAT_SERIALIZERS = {
    "dot": steps_to_dot,
    "mermaid": steps_to_mermaid,
    "tikz": steps_to_tikz,
    "plantuml": steps_to_plantuml,
    "ascii": steps_to_ascii,
}


# ─── DOT generation (Graphviz-based) ─────────────────────────────────────────


def _generate_dot_vertical(goal_text: str, steps: List[str], dpi: int = 600) -> str:
    """Generate a vertical (top-to-bottom) flowchart DOT string."""
    lines = [
        "digraph {",
        f"\tdpi={dpi}",
        f'\tgoal [label="{_wrap_text(goal_text)}" shape=ellipse]',
    ]

    prev_node = "goal"
    for i, step in enumerate(steps, 1):
        node_name = f"step_{i}"
        label = _wrap_text(f"{i}. {step}")
        lines.append(f'\t{node_name} [label="{label}" shape=box]')
        lines.append(f"\t{prev_node} -> {node_name}")
        prev_node = node_name

    lines.append("}")
    return "\n".join(lines)


def _generate_dot_horizontal(goal_text: str, steps: List[str], dpi: int = 300) -> str:
    """Generate a horizontal (left-to-right) flowchart DOT string."""
    lines = [
        "digraph {",
        f"\tdpi={dpi} rankdir=LR",
        f'\tgoal [label="{_wrap_text(goal_text, width=20)}" shape=ellipse]',
    ]

    prev_node = "goal"
    for i, step in enumerate(steps, 1):
        node_name = f"step_{i}"
        label = _wrap_text(f"{i}. {step}", width=20)
        lines.append(f'\t{node_name} [label="{label}" shape=box]')
        lines.append(f"\t{prev_node} -> {node_name}")
        prev_node = node_name

    lines.append("}")
    return "\n".join(lines)


def _generate_dot_tortuous(
    goal_text: str, steps: List[str], dpi: int = 600, cols: int = 3
) -> str:
    """Generate a tortuous (S-shaped/zigzag) flowchart DOT string.

    Matches the original FC_Attack implementation:
    - Even rows: forward edges within rank=same
    - Odd rows: reversed edge declarations with [dir=back]
    - Inter-row connectors: last node of row → first node of next row
    """
    lines = [
        "digraph {",
        f"\tdpi={dpi} rankdir=TB",
    ]

    # Build all nodes: goal + steps
    all_nodes = [("goal", _wrap_text(goal_text), "oval")] + [
        (f"step_{i}", _wrap_text(f"{i}. {step}"), "box")
        for i, step in enumerate(steps, 1)
    ]

    # Split into rows of `cols` elements
    rows = [all_nodes[i : i + cols] for i in range(0, len(all_nodes), cols)]

    for row_idx, row in enumerate(rows):
        is_even = row_idx % 2 == 0

        # Edges within this row
        if is_even:
            # Forward edges: node_0 -> node_1 -> node_2
            for i in range(len(row) - 1):
                lines.append(f"\t{row[i][0]} -> {row[i + 1][0]}")
        else:
            # Reversed declarations with dir=back (forces right-to-left ordering)
            for i in range(len(row) - 1, 0, -1):
                lines.append(f"\t{row[i][0]} -> {row[i - 1][0]} [dir=back]")

        # Inter-row connector: last of previous row → first of this row
        if row_idx > 0:
            prev_row = rows[row_idx - 1]
            lines.append(f"\t{prev_row[-1][0]} -> {row[0][0]}")

        # rank=same block with node definitions
        lines.append("\t{")
        lines.append("\t\trank=same")
        for node_name, label, shape in row:
            lines.append(
                f'\t\t{node_name} [label="{label}" '
                f"fillcolor=white shape={shape} style=filled]"
            )
        lines.append("\t}")

    lines.append("}")
    return "\n".join(lines)


def _render_dot_to_png_bytes(dot_content: str) -> bytes:
    """Render DOT content to PNG bytes using the resolved Graphviz binary."""
    dot_binary = _resolve_dot_binary()
    if not dot_binary:
        raise RuntimeError("Graphviz 'dot' binary is not available.")

    with tempfile.NamedTemporaryFile(suffix=".dot", mode="w", delete=True) as dot_file:
        dot_file.write(dot_content)
        dot_file.flush()

        env = _build_graphviz_runtime_env(dot_binary)

        system = platform.system().lower()
        format_flags = ["-Tpng:quartz", "-Tpng"] if system == "darwin" else ["-Tpng"]

        last_result: subprocess.CompletedProcess[bytes] | None = None
        for fmt in format_flags:
            result = subprocess.run(
                [dot_binary, fmt, dot_file.name],
                capture_output=True,
                timeout=30,
                env=env,
            )
            if result.returncode == 0:
                return result.stdout
            last_result = result

        if last_result is None:
            raise RuntimeError("Graphviz dot failed: no render attempts were executed")

        raise RuntimeError(
            f"Graphviz dot failed (exit {last_result.returncode}): "
            f"{last_result.stderr.decode(errors='replace')[:200]}"
        )


# ─── Public API ───────────────────────────────────────────────────────────────


def render_flowchart(
    steps: List[str],
    goal_text: str = "",
    layout: str = "vertical",
    dpi: int = 600,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Render steps as a flowchart image using Graphviz.

    Tries the system ``dot`` first. If unavailable, it can auto-download
    portable Graphviz binaries (macOS/Windows) from the latest official
    release unless ``HACKAGENT_GRAPHVIZ_AUTO_DOWNLOAD=0`` is set.

    Args:
        steps: List of step description strings.
        goal_text: The original goal/prompt displayed as the first node.
        layout: One of ``"vertical"``, ``"horizontal"``, ``"tortuous"``
            (or ``"s_shaped"`` as alias).
        dpi: Resolution for Graphviz rendering.
        **kwargs: Additional params (ignored, for backwards compat).

    Returns:
        Dict with keys:
            - image_data_url: Base64 data URL of the PNG image.
            - layout: The layout mode used.
            - num_steps: Number of steps rendered.
    """
    # Normalize layout aliases
    if layout == "s_shaped":
        layout = "tortuous"

    if not _check_graphviz():
        raise RuntimeError(
            "Graphviz 'dot' binary not found. FC-Attack looked in PATH and "
            "tried local auto-download. You can set HACKAGENT_GRAPHVIZ_DOT to "
            "a local binary path, or install Graphviz manually "
            "(e.g. 'apt install graphviz' or 'brew install graphviz'). "
            "Alternatively, use tFC-Attack which does not require image rendering."
        )

    if layout == "horizontal":
        dot = _generate_dot_horizontal(goal_text, steps, dpi=dpi)
    elif layout == "tortuous":
        dot = _generate_dot_tortuous(goal_text, steps, dpi=dpi)
    else:
        dot = _generate_dot_vertical(goal_text, steps, dpi=dpi)

    png_bytes = _render_dot_to_png_bytes(dot)
    b64_data = base64.b64encode(png_bytes).decode("utf-8")
    image_data_url = f"data:image/png;base64,{b64_data}"

    return {
        "image_data_url": image_data_url,
        "layout": layout,
        "num_steps": len(steps),
    }

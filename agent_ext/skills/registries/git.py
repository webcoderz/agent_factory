"""Git-backed skill registry — clone a remote repo and discover skills.

Clones a git repository (via subprocess, no GitPython needed) and discovers
skills from ``SKILL.md`` files within it.  Supports shallow clones, branch
selection, token auth, and SSH keys.

Example::

    from agent_ext.skills.registries.git import GitSkillsRegistry

    registry = GitSkillsRegistry(
        repo_url="https://github.com/anthropics/skills",
        path="skills",
        target_dir="./cached-skills",
    )
    registry.clone_or_pull()

    for spec in registry.list():
        print(spec.id, spec.name)
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from ..exceptions import SkillNotFoundError
from ..models import SkillSpec


@dataclass
class GitCloneOptions:
    """Options for git clone/pull operations.

    Args:
        depth: Shallow clone depth (``None`` for full clone).
        branch: Branch, tag, or ref to check out.
        single_branch: Only clone the specified branch.
        sparse_paths: Paths for sparse checkout (empty = full tree).
        env: Extra environment variables for git commands.
    """

    depth: int | None = 1
    branch: str | None = None
    single_branch: bool = True
    sparse_paths: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


def _inject_token(url: str, token: str) -> str:
    """Embed a token into an HTTPS URL."""
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        netloc = f"oauth2:{token}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def _sanitize_url(url: str) -> str:
    """Strip credentials from a URL for display."""
    parsed = urlparse(url)
    if parsed.password:
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def _run_git(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[bool, str]:
    """Run a git command, return (ok, output)."""
    full_env = {**os.environ, **(env or {})}
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=full_env, capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" if p.stdout and p.stderr else "") + (p.stderr or "")
    return p.returncode == 0, out.strip()


class GitSkillsRegistry:
    """Skills registry backed by a cloned git repository.

    Clones on first use (or when ``clone_or_pull()`` is called), then discovers
    skills from ``SKILL.md`` files within the specified ``path``.

    Args:
        repo_url: Repository URL (HTTPS or SSH).
        target_dir: Local directory for the clone (temp dir if None).
        path: Sub-path inside the repo where skills live (default: root).
        token: Personal access token for HTTPS auth (falls back to ``GITHUB_TOKEN`` env).
        ssh_key_file: Path to SSH key for SSH auth.
        clone_options: Fine-grained clone configuration.
        auto_clone: Clone immediately on construction (default True).
    """

    def __init__(
        self,
        repo_url: str,
        *,
        target_dir: str | Path | None = None,
        path: str = "",
        token: str | None = None,
        ssh_key_file: str | Path | None = None,
        clone_options: GitCloneOptions | None = None,
        auto_clone: bool = True,
    ) -> None:
        self._repo_url = repo_url
        self._path = path.strip("/")
        self._options = clone_options or GitCloneOptions()
        self._clean_url = _sanitize_url(repo_url)

        # Auth
        effective_token = token or os.environ.get("GITHUB_TOKEN")
        self._clone_url = _inject_token(repo_url, effective_token) if effective_token else repo_url

        # SSH key
        if ssh_key_file:
            key_path = Path(ssh_key_file).expanduser().resolve()
            self._options.env["GIT_SSH_COMMAND"] = f"ssh -i {key_path} -o StrictHostKeyChecking=accept-new"

        # Target directory
        self._tmp_dir: tempfile.TemporaryDirectory | None = None
        if target_dir is None:
            self._tmp_dir = tempfile.TemporaryDirectory(prefix="skills_git_")
            self._target_dir = Path(self._tmp_dir.name)
        else:
            self._target_dir = Path(target_dir).expanduser().resolve()

        self._skills: dict[str, SkillSpec] = {}

        if auto_clone:
            self.clone_or_pull()

    def __repr__(self) -> str:
        return f"GitSkillsRegistry(repo={self._clean_url!r}, path={self._path!r})"

    @property
    def skills_root(self) -> Path:
        if self._path:
            return self._target_dir / self._path
        return self._target_dir

    def _is_cloned(self) -> bool:
        return (self._target_dir / ".git").exists()

    def clone_or_pull(self) -> None:
        """Clone the repo (or pull if already cloned), then discover skills."""
        opts = self._options
        env = opts.env

        if self._is_cloned():
            # Pull
            _run_git(["git", "pull"], cwd=self._target_dir, env=env)
        else:
            # Clone
            self._target_dir.mkdir(parents=True, exist_ok=True)
            cmd = ["git", "clone"]
            if opts.depth is not None:
                cmd += ["--depth", str(opts.depth)]
            if opts.branch:
                cmd += ["--branch", opts.branch]
            if opts.single_branch:
                cmd.append("--single-branch")
            cmd += [self._clone_url, str(self._target_dir)]

            ok, out = _run_git(cmd, env=env)
            if not ok:
                # Sanitize error (don't leak tokens)
                clean_out = out.replace(self._clone_url, self._clean_url)
                raise RuntimeError(f"git clone failed: {clean_out}")

            # Sparse checkout if requested
            if opts.sparse_paths:
                _run_git(["git", "sparse-checkout", "init"], cwd=self._target_dir, env=env)
                _run_git(["git", "sparse-checkout", "set", *opts.sparse_paths], cwd=self._target_dir, env=env)

        self._discover()

    def _discover(self) -> None:
        """Discover skills from SKILL.md files in the skills root."""
        self._skills.clear()
        root = self.skills_root
        if not root.exists():
            return

        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            md_path = entry / "SKILL.md"
            if not md_path.exists():
                continue

            body = md_path.read_text(encoding="utf-8", errors="replace")
            first_line = next((ln.strip("# ").strip() for ln in body.splitlines() if ln.strip()), entry.name)
            body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

            spec = SkillSpec(
                id=entry.name,
                name=first_line or entry.name,
                description=f"Skill from {self._clean_url}: {entry.name}",
                path=str(md_path),
                metadata={
                    "body_hash": body_hash,
                    "repo": self._clean_url,
                    "registry": "git",
                },
            )
            self._skills[spec.id] = spec

    def list(self) -> list[SkillSpec]:
        return list(self._skills.values())

    def get(self, skill_id: str) -> SkillSpec:
        if skill_id not in self._skills:
            raise SkillNotFoundError(skill_id)
        return self._skills[skill_id]

    def has(self, skill_id: str) -> bool:
        return skill_id in self._skills

    def refresh(self) -> None:
        """Pull latest and re-discover skills."""
        self.clone_or_pull()

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        if self._tmp_dir:
            self._tmp_dir.cleanup()
            self._tmp_dir = None

"""Test helper: a throwaway git repo with one commit."""
import subprocess
from pathlib import Path


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    def g(*a):
        subprocess.run(["git", *a], cwd=path, check=True, capture_output=True,
                       env={**_os_environ(), **env})
    g("init", "-q", "-b", "main")
    (path / "README.md").write_text("# test repo\n", encoding="utf-8")
    (path / "src").mkdir(exist_ok=True)
    (path / "src" / "seed.py").write_text("x = 1\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-q", "-m", "seed")
    return path


def _os_environ():
    import os
    return dict(os.environ)

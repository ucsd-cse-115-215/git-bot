"""Fixture: solo-developer repo, no remote, realistically messy state.

1. No remote configured.
2. A feature branch with a non-obvious name.
3. Mixed working-tree state (staged / unstaged / untracked).
4. An untracked `scratch.md` with notes that must not be destroyed.

The fixture leaves HEAD on `main`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fixtures.builders import (
    checkout,
    checkout_new_branch,
    commit,
    init_repo,
    stage,
    write,
)


def build(path: Path) -> Path:
    repo = init_repo(path)

    # --- main: three commits, a small Python project ---
    commit(
        repo,
        "Initial commit",
        {
            "README.md": "# demo-project\n\nA toy project.\n",
            ".gitignore": "__pycache__/\n*.pyc\n",
            "src/app.py": "def main():\n    print('hello')\n",
            "src/util.py": "def greet(name):\n    return f'hi {name}'\n",
        },
        date="2026-01-10T09:00:00",
    )
    commit(
        repo,
        "Flesh out main entrypoint",
        {
            "src/app.py": (
                "from src.util import greet\n\n"
                "def main():\n"
                "    print(greet('world'))\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ),
        },
        date="2026-01-11T09:00:00",
    )
    commit(
        repo,
        "Expand README",
        {"README.md": "# demo-project\n\nA toy project. Run `python -m src.app`.\n"},
        date="2026-01-12T09:00:00",
    )

    # --- experiment-old: a distractor branch off an earlier main commit ---
    checkout_new_branch(repo, "experiment-old", start_point="main~2")
    commit(
        repo,
        "Spike: try alternate greeting",
        {"src/util.py": "def greet(name):\n    return f'yo {name}'\n"},
        date="2026-01-11T10:00:00",
    )

    # --- bigframes-refactor: the branch the user actually wants ---
    checkout(repo, "main")
    checkout_new_branch(repo, "bigframes-refactor")
    commit(
        repo,
        "Start refactor: split app into modules",
        {
            "src/app.py": (
                "from src.util import greet\n"
                "from src.cli import run\n\n"
                "def main():\n"
                "    run(greet)\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ),
            "src/cli.py": (
                "def run(greeter):\n"
                "    print(greeter('world'))\n"
            ),
        },
        date="2026-01-14T09:00:00",
    )

    # --- back on main with a messy working tree ---
    checkout(repo, "main")
    stage(
        repo,
        "README.md",
        "# demo-project\n\nA toy project. Run `python -m src.app` to say hello.\n",
    )
    write(
        repo,
        "src/app.py",
        (
            "from src.util import greet\n\n"
            "def main():\n"
            "    print(greet('world'))\n"
            "    print('goodbye')\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        ),
    )
    write(
        repo,
        "scratch.md",
        "# ideas\n\n- try a plugin system\n- look into async greetings\n- TODO: ask Sam about the API\n",
    )

    return repo


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m fixtures.messy_solo <path>", file=sys.stderr)
        sys.exit(2)
    out = build(Path(sys.argv[1]).resolve())
    print(f"Built messy_solo fixture at {out}")

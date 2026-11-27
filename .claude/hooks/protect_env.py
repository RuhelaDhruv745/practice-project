"""PreToolUse hook: block access to .env files. .env.example is allowed.

Exit 2 blocks the tool call. Shell commands are checked as text only.
"""

import json
import re
import sys
from fnmatch import fnmatchcase

MESSAGE = (
    "Blocked: .env holds secrets, so it must not be read, edited, written or used "
    "in a shell command. Use .env.example for variable names, or ask the user to "
    "change .env themselves."
)
SEPARATORS = r"[\s\"'`=<>|;&(){}\[\],@]+"


def is_secret_name(name):
    # Windows ignores case, trailing dots/spaces and ":stream" suffixes.
    name = name.split(":")[0].rstrip(". ").lower()
    return name != ".env.example" and (name == ".env" or name.startswith(".env."))


def path_is_secret(path):
    path = re.sub(r"^[A-Za-z]:", "", path)
    return is_secret_name(re.split(r"[\\/]", path.rstrip("\\/"))[-1])


def wildcard_hits_env(part):
    part = part.lower()
    if not ("*" in part or "?" in part) or not (".e" in part or "env" in part):
        return False
    return any(fnmatchcase(name, part) for name in (".env", ".env.local"))


def text_mentions_env(text):
    for token in re.split(SEPARATORS, text):
        for part in re.split(r"[\\/:]", token):
            if is_secret_name(part) or wildcard_hits_env(part):
                return True
    return False


def should_block(data):
    tool = data["tool_name"]
    args = data["tool_input"]
    if any(
        path_is_secret(args.get(k) or "")
        for k in ("file_path", "notebook_path", "path")
    ):
        return True
    text_keys = ["command", "glob"]
    if tool == "Glob":  # Grep's "pattern" is a search term, not a file name.
        text_keys.append("pattern")
    return any(text_mentions_env(args.get(k) or "") for k in text_keys)


def main():
    try:
        blocked = should_block(json.loads(sys.stdin.buffer.read().decode("utf-8")))
    except Exception as error:  # noqa: BLE001 - fail closed on any error
        print(
            f"Blocked: the .env guard could not check this call ({error!r}).",
            file=sys.stderr,
        )
        return 2
    if blocked:
        print(MESSAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

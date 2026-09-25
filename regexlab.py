#!/usr/bin/env python3
"""RegexLab - a dependency-free regex tester, explainer and recipe library.

Python 3 standard library only. No network access, no accounts, no secrets.
"""

import argparse
import json
import re
import sys

VERSION = "1.0.0"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - older interpreters / redirected streams
    pass


# ---------------------------------------------------------------------------
# Recipe library
# ---------------------------------------------------------------------------

RECIPES = [
    {
        "id": "email",
        "title": "Validate an email address",
        "pattern": r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
        "flavor": "JavaScript (ECMAScript) compatible, pragmatic RFC 5222 subset",
        "notes": (
            "The famous StackOverflow answer. Deliberately pragmatic: it rejects "
            "obvious junk without attempting the full RFC 5322 grammar (comments, "
            "quoted local parts, domain literals)."
        ),
        "examples": [
            ("user@example.com", True),
            ("first.last+tag@sub.domain.co", True),
            ("no-at-sign.example.com", False),
            ("two@@at.com", False),
            ("trailingdot@example.c", False),
        ],
    },
    {
        "id": "no-word",
        "title": "Match a line that does NOT contain a word",
        "pattern": r"^(?!.*\bword\b).*$",
        "flavor": "any engine with negative lookahead (Python, JS, PCRE, ripgrep)",
        "notes": (
            "Anchored negative lookahead: the line must not have 'word' anywhere. "
            "Replace 'word' with your term. Add the 'm' flag so '.' and '^'/'$' "
            "behave per line when scanning multi-line text."
        ),
        "examples": [
            ("this line is fine", True),
            ("this line has a word inside", False),
            ("word at the start", False),
        ],
    },
    {
        "id": "digits",
        "title": "Digits only",
        "pattern": r"^\d+$",
        "flavor": "universal",
        "notes": "Use ^...$ (or \\A...\\z in Python) so the whole string must match.",
        "examples": [("12345", True), ("12a45", False), ("", False)],
    },
    {
        "id": "date-iso",
        "title": "ISO date YYYY-MM-DD",
        "pattern": r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        "flavor": "universal",
        "notes": "Checks shape and calendar ranges, not leap years.",
        "examples": [
            ("2026-09-25", True),
            ("2026-13-01", False),
            ("25/09/2026", False),
        ],
    },
    {
        "id": "url",
        "title": "HTTP(S) URL",
        "pattern": r"^https?://[A-Za-z0-9.-]+(:\d{1,5})?(/[^?\s]*)?(\?[^#\s]*)?(#\S*)?$",
        "flavor": "universal",
        "notes": "Practical shape check for forms; not a full RFC 3986 validator.",
        "examples": [
            ("https://example.com/path?q=1#top", True),
            ("ftp://example.com", False),
            ("https://", False),
        ],
    },
    {
        "id": "duplicate-word",
        "title": "Repeated word ('the the')",
        "pattern": r"\b(\w+)\s+\1\b",
        "flavor": "universal (backreference \\1)",
        "notes": "Classic typo detector. Case-insensitive (-i) to catch 'The the'.",
        "examples": [
            ("this is is the the end", True),
            ("this is the end", False),
        ],
    },
    {
        "id": "ipv4",
        "title": "IPv4 address",
        "pattern": r"\b((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b",
        "flavor": "universal",
        "notes": "Each octet is restricted to 0-255.",
        "examples": [
            ("192.168.0.1", True),
            ("999.1.1.1", False),
        ],
    },
    {
        "id": "extract-groups",
        "title": "Capture structured fields",
        "pattern": r"(?P<key>[A-Za-z_][\w]*)\s*=\s*(?P<value>\"[^\"]*\"|\S+)",
        "flavor": "Python named groups (JS: use numbered groups)",
        "notes": "Use named groups to read fields by name from the match object.",
        "examples": [
            ('name = "Ada"', True),
            ("bareword", False),
        ],
    },
    {
        "id": "quoted-string",
        "title": "Quoted string",
        "pattern": r"\"(?:\\.|[^\"\\])*\"",
        "flavor": "universal",
        "notes": "Handles escaped quotes inside the string.",
        "examples": [('"say \\"hi\\" now"', True), ('"unterminated', False)],
    },
]

CHEATSHEET = [
    (".", "Any character except newline"),
    ("\\d / \\D", "Digit / not a digit"),
    ("\\w / \\W", "Word character [A-Za-z0-9_] / not"),
    ("\\s / \\S", "Whitespace / not whitespace"),
    ("^ / $", "Start / end of string (per line with the m flag)"),
    ("\\b / \\B", "Word boundary / not a word boundary"),
    ("[abc] / [^abc]", "Character class / negated class"),
    ("[a-z]", "Range inside a class"),
    ("*", "Zero or more"),
    ("+", "One or more"),
    ("?", "Zero or one"),
    ("{n}", "Exactly n"),
    ("{n,}", "At least n"),
    ("{n,m}", "Between n and m"),
    ("*?  +?  ??  {n,m}?", "Lazy (non-greedy) versions of the quantifiers"),
    ("|", "Alternation - either side"),
    ("(...)", "Capturing group"),
    ("(?:...)", "Non-capturing group"),
    ("(?P<name>...)", "Named group (Python); (?<name>...) in modern JS"),
    ("(?!...) / (?=...)", "Negative / positive lookahead"),
    ("(?<!...) / (?<=...)", "Negative / positive lookbehind"),
    ("\\1 ... \\9", "Backreference to a captured group"),
    ("(?i) / (?m) / (?s)", "Inline flags: ignore case / multiline / dot matches newline"),
]


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


class RegexLabError(Exception):
    """User-facing error with a clean message."""


def flag_chars(args):
    chars = ""
    for name in ("ignore_case", "multiline", "dotall", "ascii", "verbose"):
        if getattr(args, name, False):
            chars += {"ignore_case": "i", "multiline": "m", "dotall": "s",
                      "ascii": "a", "verbose": "x"}[name]
    return chars


def compile_pattern(pattern, args):
    flags = 0
    for attr, flag in (("ignore_case", re.IGNORECASE), ("multiline", re.MULTILINE),
                       ("dotall", re.DOTALL), ("ascii", re.ASCII),
                       ("verbose", re.VERBOSE)):
        if getattr(args, attr, False):
            flags |= flag
    if not pattern:
        raise RegexLabError("empty pattern")
    try:
        return re.compile(pattern, flags)
    except re.error as exc:
        pos = getattr(exc, "pos", None)
        hint = ""
        if pos is not None:
            col = getattr(exc, "colno", pos + 1)
            caret = " " * (col - 1) + "^"
            hint = "\n  " + pattern + "\n  " + caret
        raise RegexLabError("invalid pattern: %s%s" % (exc, hint)) from exc


def read_inputs(args):
    if args.file:
        if args.file == "-":
            return sys.stdin.read().splitlines()
        try:
            with open(args.file, "r", encoding="utf-8") as handle:
                return handle.read().splitlines()
        except OSError as exc:
            raise RegexLabError("cannot read file: %s" % exc) from exc
    if args.inputs:
        return list(args.inputs)
    if sys.stdin.isatty():
        raise RegexLabError(
            "no input given; pass strings as arguments, use --file, or pipe via stdin")
    return sys.stdin.read().splitlines()


def match_dict(match):
    return {
        "match": match.group(0),
        "start": match.start(),
        "end": match.end(),
        "groups": list(match.groups()),
        "named": {k: v for k, v in match.groupdict().items() if v is not None},
    }


# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------

_ESCAPES = {
    "d": "a digit (0-9)", "D": "a non-digit", "w": "a word character (a-z, A-Z, 0-9, _)",
    "W": "a non-word character", "s": "whitespace (space, tab, newline)",
    "S": "a non-whitespace character", "b": "a word boundary", "B": "not a word boundary",
    "A": "the very start of the string", "z": "the very end of the string",
    "n": "a newline", "t": "a tab", "r": "a carriage return",
    "0": "the end of the string (backreference 0)",
}


def _read_class(pattern, i):
    """pattern[i] == '['. Returns (text, next_index)."""
    j = i + 1
    if j < len(pattern) and pattern[j] == "^":
        j += 1
    if j < len(pattern) and pattern[j] == "]":
        j += 1
    while j < len(pattern) and pattern[j] != "]":
        if pattern[j] == "\\":
            j += 1
        j += 1
    j = min(j, len(pattern))
    return pattern[i:j + 1], j + 1


def explain(pattern):
    """Return a list of human-readable lines describing each token."""
    lines = []
    i, n = 0, len(pattern)
    group_no = 0

    def add(text):
        lines.append("%2d. %s" % (len(lines) + 1, text))

    while i < n:
        c = pattern[i]

        if c == "\\":
            nxt = pattern[i + 1] if i + 1 < n else ""
            if nxt and nxt.isdigit() and nxt != "0":
                add("backreference to group %s" % nxt)
            elif nxt in _ESCAPES:
                add("escape \\%s - matches %s" % (nxt, _ESCAPES[nxt]))
            elif nxt:
                add("escaped literal '%s'" % nxt)
            else:
                add("trailing backslash (incomplete escape)")
            i += 2

        elif c == "[":
            text, i = _read_class(pattern, i)
            negated = text.startswith("[^")
            body = text[2:] if negated else text[1:]
            body = body[:-1] if body.endswith("]") else body
            what = ("none of: " if negated else "one of: ") + (body or "empty")
            add("character class %s" % what)

        elif c == "(":
            rest = pattern[i:]
            if rest.startswith("(?P<"):
                end = rest.find(">")
                name = rest[4:end] if end != -1 else "?"
                add("start of capturing group %d named '%s'" % (group_no + 1, name))
                group_no += 1
                i = end + 1 if end != -1 else i + 4
            elif rest.startswith("(?<") and not rest.startswith(("(?<!", "(?<=")):
                end = rest.find(">")
                name = rest[3:end] if end != -1 else "?"
                add("start of capturing group %d named '%s'" % (group_no + 1, name))
                group_no += 1
                i = end + 1 if end != -1 else i + 3
            elif rest.startswith("(?:"):
                add("start of a non-capturing group (grouping only)")
                i += 3
            elif rest.startswith("(?="):
                add("start of positive lookahead - following text must match, not consumed")
                i += 3
            elif rest.startswith("(?!"):
                add("start of negative lookahead - following text must NOT match")
                i += 3
            elif rest.startswith("(?<="):
                add("start of positive lookbehind - preceding text must match")
                i += 4
            elif rest.startswith("(?<!"):
                add("start of negative lookbehind - preceding text must NOT match")
                i += 4
            elif rest.startswith("(?#"):
                end = rest.find(")")
                add("comment: %s" % rest[3:end if end != -1 else None])
                i = (end + 1) if end != -1 else n
            elif rest.startswith("(?"):
                end = rest.find(")")
                add("inline group directive: %s" % rest[:end + 1 if end != -1 else 4])
                i = (end + 1) if end != -1 else i + 2
            else:
                group_no += 1
                add("start of capturing group %d" % group_no)
                i += 1

        elif c == ")":
            add("end of the current group")
            i += 1

        elif c == "|":
            add("alternation - the pattern to the right is an alternative")
            i += 1

        elif c in "*+?":
            lazy = i + 1 < n and pattern[i + 1] == "?"
            names = {"*": "zero or more", "+": "one or more", "?": "zero or one"}
            add("quantifier: %s (%s)%s" % (names[c], c, " - lazy, match as little as possible" if lazy else ""))
            i += 2 if lazy else 1

        elif c == "{":
            m = re.match(r"\{(\d*)(,?)(\d*)\}", pattern[i:])
            if m:
                lo, comma, hi = m.group(1), m.group(2), m.group(3)
                if comma and hi:
                    desc = "between %s and %s times" % (lo or "0", hi)
                elif comma:
                    desc = "%s or more times" % (lo or "0")
                else:
                    desc = "exactly %s time(s)" % lo
                lazy = i + m.end() < n and pattern[i + m.end()] == "?"
                add("quantifier: %s%s" % (desc, " - lazy" if lazy else ""))
                i += m.end() + (1 if lazy else 0)
            else:
                add("literal '{'")
                i += 1

        elif c == "^":
            add("anchor: start of string (per line with the m flag)")
            i += 1
        elif c == "$":
            add("anchor: end of string (per line with the m flag)")
            i += 1
        elif c == ".":
            add("any character except newline (any character at all with the s flag)")
            i += 1
        else:
            run = []
            while i < n and pattern[i] not in "\\.^$[]()|*+?{":
                run.append(pattern[i])
                i += 1
            add("literal text: %s" % "".join(run))

    if not lines:
        add("empty pattern - matches the empty string only")
    return lines


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_check(args):
    compile_pattern(args.pattern, args)
    flags = flag_chars(args) or "-"
    result = {"valid": True, "pattern": args.pattern, "flags": flags}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("OK: pattern compiles (flags: %s)" % flags)
    return 0


def cmd_explain(args):
    if not args.pattern:
        raise RegexLabError("no pattern given")
    lines = explain(args.pattern)
    if args.json:
        print(json.dumps({"pattern": args.pattern, "steps": lines}, indent=2))
    else:
        print("Pattern: %s" % args.pattern)
        for line in lines:
            print("  %s" % line)
    return 0


def cmd_match(args):
    regex = compile_pattern(args.pattern, args)
    inputs = read_inputs(args)
    if not inputs:
        raise RegexLabError("no input to test against")

    report = {"pattern": args.pattern, "flags": flag_chars(args), "results": []}
    any_match = False

    for text in inputs:
        matches = [match_dict(m) for m in regex.finditer(text)]
        if args.limit is not None:
            matches = matches[:args.limit]
        if matches:
            any_match = True
        entry = {"input": text, "matched": bool(matches), "matches": matches}
        report["results"].append(entry)

        if not args.json and not args.files_only:
            print("INPUT   %s" % text)
            if not matches:
                print("        no match")
            elif args.replace is not None:
                print("        replaced -> %s" % regex.sub(args.replace, text))
            else:
                for m in matches:
                    print("        match %r at [%d:%d]" % (m["match"], m["start"], m["end"]))
                    for idx, value in enumerate(m["groups"], start=1):
                        print("          group %d = %r" % (idx, value))
                    if m["named"]:
                        for key, value in m["named"].items():
                            print("          group %s = %r" % (key, value))
            print("")

    if args.json:
        print(json.dumps(report, indent=2))
    elif args.files_only:
        for entry in report["results"]:
            if entry["matched"]:
                print(entry["input"])
    return 0 if any_match else 1


def cmd_recipes(args):
    if args.id:
        wanted = [r for r in RECIPES if r["id"] == args.id]
        if not wanted:
            raise RegexLabError("unknown recipe id: %s (try: %s)"
                                % (args.id, ", ".join(r["id"] for r in RECIPES)))
        chosen = wanted
    else:
        chosen = RECIPES

    if args.json:
        print(json.dumps(chosen, indent=2))
        return 0

    for recipe in chosen:
        print("== %s (%s)" % (recipe["title"], recipe["id"]))
        print("   pattern: %s" % recipe["pattern"])
        print("   flavor : %s" % recipe["flavor"])
        print("   %s" % recipe["notes"])
        for sample, expected in recipe["examples"]:
            try:
                ok = bool(re.search(recipe["pattern"], sample))
            except re.error:
                ok = None
            verdict = "matches" if ok else "no match"
            flag = "ok" if ok == expected else "UNEXPECTED"
            print("      %-40r -> %-9s (expected %s) %s"
                  % (sample, verdict, "match" if expected else "no match", flag))
        print("")
    return 0


def cmd_cheatsheet(args):
    if args.json:
        print(json.dumps([{"token": a, "meaning": b} for a, b in CHEATSHEET], indent=2))
        return 0
    width = max(len(a) for a, _ in CHEATSHEET)
    for token, meaning in CHEATSHEET:
        print("%-*s  %s" % (width, token, meaning))
    return 0


def cmd_selfcheck(args):
    failures = []

    def check(label, condition, detail=""):
        if condition:
            print("  PASS  %s" % label)
        else:
            print("  FAIL  %s %s" % (label, detail))
            failures.append(label)

    print("RegexLab self-check (version %s)" % VERSION)

    # Every recipe must compile and behave as advertised.
    for recipe in RECIPES:
        try:
            regex = re.compile(recipe["pattern"])
        except re.error as exc:
            check("recipe %s compiles" % recipe["id"], False, str(exc))
            continue
        ok = True
        for sample, expected in recipe["examples"]:
            if bool(regex.search(sample)) != expected:
                ok = False
                check("recipe %s example %r" % (recipe["id"], sample), False,
                      "expected match=%s" % expected)
        if ok:
            check("recipe %s examples" % recipe["id"], True)

    # Explainer must terminate, stay ordered and cover the whole pattern.
    for sample in [r"a(b|c)+d", r"^\d{3}-\d{4}$", r"(?P<n>x)\s*\1",
                   r"^(?!.*word\b).*$", r"[^a-z]{2,?}", "\\", "(){}[]|*+?.^$"]:
        steps = explain(sample)
        check("explain(%r) produces steps" % sample, len(steps) > 0)
        check("explain(%r) numbers steps sequentially" % sample,
              [s.split(".", 1)[0].strip() for s in steps] ==
              [str(i) for i in range(1, len(steps) + 1)])

    # Core behaviours.
    check("match finds span", re.search(r"\d+", "ab123cd").span() == (2, 5))
    check("flags ignore case", bool(re.search("abc", "ABC", re.IGNORECASE)))
    check("negative lookahead works", not re.search(r"^(?!.*\bword\b).*$", "has word here"))
    loaded = [name for name in ("urllib", "http", "socket", "requests")
              if any(key == name or key.startswith(name + ".") for key in sys.modules)]
    check("no network modules imported", not loaded, "loaded: %s" % ", ".join(loaded))

    if failures:
        print("\n%d check(s) FAILED" % len(failures))
        return 1
    print("\nAll checks passed.")
    return 0


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def add_flags(parser):
    group = parser.add_argument_group("regex flags")
    group.add_argument("-i", "--ignore-case", action="store_true", help="case-insensitive match")
    group.add_argument("-m", "--multiline", action="store_true", help="^ and $ match per line")
    group.add_argument("-s", "--dotall", action="store_true", help="'.' also matches newline")
    group.add_argument("-a", "--ascii", action="store_true", help=r"\w \d \s use ASCII only")
    group.add_argument("-x", "--verbose", action="store_true", help="ignore whitespace/comments in pattern")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="regexlab",
        description="RegexLab: test, explain and look up regular expressions.",
        epilog="Examples:\n"
               "  python regexlab.py check '^\\d{3}-\\d{4}$'\n"
               "  python regexlab.py explain '^(?!.*\\bword\\b).*$'\n"
               "  python regexlab.py match -i 'a.c' abc aXc nope\n"
               "  python regexlab.py recipes --id email\n"
               "  python regexlab.py cheatsheet\n"
               "  python regexlab.py selfcheck\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version="regexlab " + VERSION)
    sub = parser.add_subparsers(dest="command", metavar="command")

    p = sub.add_parser("check", help="validate that a pattern compiles")
    p.add_argument("pattern")
    add_flags(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("explain", help="break a pattern down token by token")
    p.add_argument("pattern")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("match", help="test a pattern against input strings")
    p.add_argument("pattern")
    p.add_argument("inputs", nargs="*", help="strings to test (default: stdin)")
    p.add_argument("--file", "-f", help="read input lines from a file ('-' for stdin)")
    p.add_argument("--replace", "-r", metavar="REPL",
                   help="show regex.sub output instead of match details")
    p.add_argument("--limit", "-n", type=int, default=None, metavar="K",
                   help="report at most K matches per input")
    p.add_argument("--files-only", action="store_true",
                   help="print only inputs that matched")
    add_flags(p)
    p.set_defaults(func=cmd_match)

    p = sub.add_parser("recipes", help="show ready-made patterns with examples")
    p.add_argument("--id", help="show a single recipe by id")
    add_flags(p)
    p.set_defaults(func=cmd_recipes)

    p = sub.add_parser("cheatsheet", help="print a token reference")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p.set_defaults(func=cmd_cheatsheet)

    p = sub.add_parser("selfcheck", help="run built-in automated checks")
    p.set_defaults(func=cmd_selfcheck)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except RegexLabError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except BrokenPipeError:  # pragma: no cover
        return 0
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":
    sys.exit(main())

# RegexLab

Test, explain, and look up regular expressions — from the terminal or a single HTML file.

Two entry points, zero dependencies, no network calls, no accounts:

| File | What it is |
|------|------------|
| `regexlab.py` | Command-line tester, explainer, recipe library, cheatsheet |
| `index.html` | Single-file browser tester (open it directly, works offline) |

## Requirements

- Python 3.10+ (standard library only) for the CLI
- Any modern browser for `index.html`
- Optional: Node.js, only so the test suite can syntax-check the embedded JavaScript

## Install

No installation step. Clone/download and run:

```bash
cd products/regexlab
python regexlab.py --version
```

Optionally add it to your PATH:

```bash
# Linux/macOS
chmod +x regexlab.py && ln -s "$PWD/regexlab.py" ~/.local/bin/regexlab

# Windows (PowerShell)
# add this folder to your PATH, then call: regexlab <command>
```

## Usage

```
python regexlab.py <command> [options]

commands:
  check      validate that a pattern compiles
  explain    break a pattern down token by token
  match      test a pattern against input strings
  recipes    show ready-made patterns with examples
  cheatsheet print a token reference
  selfcheck  run built-in automated checks
```

Common flags (on `check`, `match`, `recipes`):

```
-i  --ignore-case   case-insensitive
-m  --multiline     ^ and $ match per line
-s  --dotall        '.' also matches newline
-a  --ascii         \w \d \s use ASCII only
-x  --verbose       ignore whitespace/comments in pattern
    --json          machine-readable output
```

### Examples

**Validate a pattern**

```bash
$ python regexlab.py check '^\d{3}-\d{4}$'
OK: pattern compiles (flags: -)

$ python regexlab.py check '['
error: invalid pattern: unterminated character set at position 0
  [
  ^
```

**Test a pattern against strings**

```bash
$ python regexlab.py match -i 'a.c' abc aXc nope
INPUT   abc
        match 'abc' at [0:3]

INPUT   aXc
        match 'aXc' at [0:3]

INPUT   nope
        no match
```

Exit code is `0` when at least one input matched, `1` when nothing matched, `2` on
usage/compile errors — so it drops straight into shell scripts and CI.

**Pipe lines in, filter them out**

```bash
$ echo -e "user@example.com\nnot-an-email" | python regexlab.py match --files-only '^[^@]+@[^@]+\.[a-z]{2,}$'
user@example.com

$ python regexlab.py match -r '#' '\d+' 'order 12345 shipped'
INPUT   order 12345 shipped
        replaced -> order # shipped
```

**Read a file / emit JSON**

```bash
$ python regexlab.py match --file app.log 'ERROR|FATAL'
$ python regexlab.py match --json '(\w+)@(\w+)' 'mail bob@site' | python -m json.tool
```

**Explain a pattern token by token**

```bash
$ python regexlab.py explain '^(?!.*\bword\b).*$'
Pattern: ^(?!.*\bword\b).*$
   1. anchor: start of string (per line with the m flag)
   2. start of negative lookahead - following text must NOT match
   3. any character except newline (any character at all with the s flag)
   4. quantifier: zero or more (*)
   5. escape \b - matches a word boundary
   6. literal text: word
   7. escape \b - matches a word boundary
   8. end of the current group
   9. any character except newline (any character at all with the s flag)
  10. quantifier: zero or more (*)
  11. anchor: end of string (per line with the m flag)
```

**Recipes** — curated patterns with notes and live-checked examples

```bash
$ python regexlab.py recipes            # list everything
$ python regexlab.py recipes --id email # one recipe in detail
```

Included: `email`, `no-word` (line that does not contain a word), `digits`,
`date-iso`, `url`, `duplicate-word`, `ipv4`, `extract-groups`, `quoted-string`.

**Cheatsheet**

```bash
$ python regexlab.py cheatsheet
.                    Any character except newline
\d / \D              Digit / not a digit
\b / \B              Word boundary / not a word boundary
*?  +?  ??  {n,m}?   Lazy (non-greedy) versions of the quantifiers
...
```

### Browser tool

Double-click `index.html` (or drag it into a browser). Paste a pattern and a test
string, tick the flags, and matches highlight live with capture groups listed
underneath. A recipe dropdown and cheat sheet are built in. Everything runs
locally in the page — no requests, no storage, no telemetry.

## Tests

Two layers of automated checks:

```bash
# full suite (35 tests: CLI behaviour, explainer, recipes, HTML/JS constraints)
python -m unittest discover -v

# built-in self-check, no test runner needed
python regexlab.py selfcheck
```

The suite also enforces the project constraints: only standard-library imports in
`regexlab.py`, no network/credential code, and no remote assets in `index.html`.

## Design notes

- Pure `re` module; no third-party regex engine, no paid APIs, no accounts.
- Nothing is written to disk; the tool keeps no state, keys, or personal data.
- `explain` is a small hand-rolled tokenizer: it never executes the pattern and
  always terminates, even on malformed input like `\` or `(?:`.
- The browser tool intentionally uses JavaScript's `RegExp`, so patterns behave
  the way they will in front-end code.

## Pricing

`$9 one-time` — buy once, run locally, no subscription. Checkout activates on the
[landing page](LANDING.html) once payments are connected; the browser tool stays free.

## License

No `LICENSE` file is included yet; licensing terms are decided by the repository owner.

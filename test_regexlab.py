"""Automated tests for RegexLab.

Run with either:
    python -m unittest discover -v
    python test_regexlab.py -v
"""

import io
import json
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr

import regexlab


class ExplainTests(unittest.TestCase):
    def test_steps_are_numbered_sequentially(self):
        steps = regexlab.explain(r"a(b|c)+d")
        numbers = [s.split(".", 1)[0].strip() for s in steps]
        self.assertEqual(numbers, [str(i) for i in range(1, len(steps) + 1)])

    def test_explains_lookahead_recipe(self):
        text = "\n".join(regexlab.explain(r"^(?!.*\bword\b).*$"))
        self.assertIn("negative lookahead", text)
        self.assertIn("anchor", text)

    def test_explains_named_group_and_backreference(self):
        text = "\n".join(regexlab.explain(r"(?P<k>\w+)\s+\1"))
        self.assertIn("named 'k'", text)
        self.assertIn("backreference to group 1", text)

    def test_explains_character_class_quantifier_and_alternation(self):
        text = "\n".join(regexlab.explain(r"[^a-z]{2,3}|x"))
        self.assertIn("character class none of:", text)
        self.assertIn("between 2 and 3 times", text)
        self.assertIn("alternation", text)

    def test_handles_broken_pattern_without_crashing(self):
        for pattern in ["\\", "(", "[", "{2}", "(?", "(?P<>x)"]:
            steps = regexlab.explain(pattern)
            self.assertTrue(steps, "no steps for %r" % pattern)

    def test_empty_pattern(self):
        self.assertIn("empty pattern", regexlab.explain("")[0])


class RecipeTests(unittest.TestCase):
    def test_all_recipes_compile(self):
        for recipe in regexlab.RECIPES:
            re.compile(recipe["pattern"])

    def test_all_recipes_have_unique_ids_and_examples(self):
        ids = [r["id"] for r in regexlab.RECIPES]
        self.assertEqual(len(ids), len(set(ids)))
        for recipe in regexlab.RECIPES:
            self.assertTrue(recipe["examples"], recipe["id"])
            self.assertTrue(recipe["notes"], recipe["id"])

    def test_recipes_match_their_examples(self):
        for recipe in regexlab.RECIPES:
            regex = re.compile(recipe["pattern"])
            for sample, expected in recipe["examples"]:
                self.assertEqual(
                    bool(regex.search(sample)), expected,
                    "%s: %r should be match=%s" % (recipe["id"], sample, expected))

    def test_email_recipe_handles_common_cases(self):
        regex = re.compile(next(r for r in regexlab.RECIPES if r["id"] == "email")["pattern"])
        self.assertTrue(regex.match("developer@example.com"))
        self.assertFalse(regex.match("developer@example"))

    def test_no_word_recipe(self):
        regex = re.compile(next(r for r in regexlab.RECIPES if r["id"] == "no-word")["pattern"])
        self.assertTrue(regex.match("clean line"))
        self.assertFalse(regex.match("contains word here"))


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = regexlab.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_check_valid_pattern(self):
        code, out, _ = self.run_cli("check", r"^\d{3}$")
        self.assertEqual(code, 0)
        self.assertIn("OK", out)

    def test_check_invalid_pattern_returns_error_code(self):
        code, _, err = self.run_cli("check", "[")
        self.assertEqual(code, 2)
        self.assertIn("invalid pattern", err)
        self.assertIn("^", err)

    def test_match_reports_hits_and_misses(self):
        code, out, _ = self.run_cli("match", r"\d+", "abc", "a12b")
        self.assertEqual(code, 0)
        self.assertIn("no match", out)
        self.assertIn("match '12'", out)

    def test_match_exit_code_when_nothing_matches(self):
        code, out, _ = self.run_cli("match", r"zzz", "abc")
        self.assertEqual(code, 1)
        self.assertIn("no match", out)

    def test_match_with_ignore_case_flag(self):
        code, out, _ = self.run_cli("match", "-i", "abc", "ABC")
        self.assertEqual(code, 0)
        self.assertIn("match 'ABC'", out)

    def test_match_json_output(self):
        code, out, _ = self.run_cli("match", "--json", r"(\w+)@(\w+)", "mail me at bob@site")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["results"][0]["matched"])
        self.assertEqual(payload["results"][0]["matches"][0]["groups"], ["bob", "site"])

    def test_match_replace(self):
        code, out, _ = self.run_cli("match", "-r", "#", r"\d+", "a1b22c")
        self.assertEqual(code, 0)
        self.assertIn("replaced -> a#b#c", out)

    def test_match_files_only(self):
        code, out, _ = self.run_cli("match", "--files-only", r"\d+", "abc", "a1")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "a1")

    def test_match_stdin(self):
        buffer_in = io.StringIO("one\ntwo2\n")
        buffer_in.isatty = lambda: False
        buffer_out = io.StringIO()
        old = sys.stdin
        sys.stdin = buffer_in
        try:
            with redirect_stdout(buffer_out):
                code = regexlab.main(["match", r"\d"])
        finally:
            sys.stdin = old
        self.assertEqual(code, 0)
        self.assertIn("match '2'", buffer_out.getvalue())

    def test_match_without_input_fails_cleanly(self):
        buffer_in = io.StringIO("")
        buffer_in.isatty = lambda: True
        old = sys.stdin
        sys.stdin = buffer_in
        try:
            code, _, err = self.run_cli("match", r"\d")
        finally:
            sys.stdin = old
        self.assertEqual(code, 2)
        self.assertIn("no input given", err)

    def test_recipes_by_id(self):
        code, out, _ = self.run_cli("recipes", "--id", "email")
        self.assertEqual(code, 0)
        self.assertIn("Validate an email address", out)
        self.assertIn("ok", out)

    def test_recipes_unknown_id_fails_cleanly(self):
        code, _, err = self.run_cli("recipes", "--id", "nope")
        self.assertEqual(code, 2)
        self.assertIn("unknown recipe id", err)

    def test_help_examples_parse_with_real_flags(self):
        import shlex

        parser = regexlab.build_parser()
        epilog = parser.epilog or ""
        examples = [
            line.strip()
            for line in epilog.splitlines()
            if line.strip().startswith("python regexlab.py")
        ]
        self.assertGreaterEqual(len(examples), 5)
        for line in examples:
            argv = shlex.split(line)[2:]
            try:
                parser.parse_args(argv)
            except SystemExit as exc:
                self.fail(
                    "help example rejected by argparse: %r (exit %s)" % (line, exc.code)
                )

    def test_cheatsheet_contains_core_tokens(self):
        code, out, _ = self.run_cli("cheatsheet")
        self.assertEqual(code, 0)
        self.assertIn("Word boundary", out)
        self.assertIn("Lazy", out)

    def test_explain_command(self):
        code, out, _ = self.run_cli("explain", r"a+b")
        self.assertEqual(code, 0)
        self.assertIn("quantifier", out)

    def test_selfcheck_passes(self):
        code, out, _ = self.run_cli("selfcheck")
        self.assertEqual(code, 0)
        self.assertIn("All checks passed", out)

    def test_no_command_prints_help(self):
        code, out, _ = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn("usage:", out)


class SubprocessTests(unittest.TestCase):
    def test_module_runs_as_script(self):
        result = subprocess.run(
            [sys.executable, "regexlab.py", "check", r"^[a-z]+$"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)

    def test_subprocess_match_pipeline(self):
        result = subprocess.run(
            [sys.executable, "regexlab.py", "match", r"^\d{3}-\d{4}$", "123-4567", "12-3456"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("match '123-4567'", result.stdout)
        self.assertIn("no match", result.stdout)


def _read(name):
    with open(name, "r", encoding="utf-8") as handle:
        return handle.read()


class HtmlToolTests(unittest.TestCase):
    def test_html_is_single_file_with_no_remote_assets(self):
        source = _read("index.html")
        self.assertNotIn("<script src", source.lower())
        self.assertNotIn("<link rel=\"stylesheet\"", source.lower())
        self.assertNotIn("fetch(", source)
        self.assertNotIn("xmlhttprequest", source.lower())
        self.assertNotIn("import ", source.split("<script>")[1])

    def test_every_element_id_referenced_by_js_exists(self):
        source = _read("index.html")
        script = source.split("<script>", 1)[1]
        used = set(re.findall(r'\$\("([\w-]+)"\)', script)) | set(
            re.findall(r'getElementById\("([\w-]+)"\)', script))
        dynamic = {k for k in ("f_i", "f_g", "f_m", "f_s", "f_u")}
        present = set(re.findall(r'id="([\w-]+)"', source)) | dynamic
        missing = used - present
        self.assertFalse(missing, "missing element ids: %s" % sorted(missing))

    def test_recipes_embedded_in_html_compile_in_javascript_engine(self):
        if not self._node():
            self.skipTest("node not available")
        script = (
            'const fs = require("fs");'
            'const src = fs.readFileSync(process.argv[1], "utf8");'
            'const block = src.split("const RECIPES = [")[1].split("\\n];")[0];'
            'const found = block.match(/pattern:\\s*"((?:[^"\\\\]|\\\\.)*)"/g) || [];'
            'const patterns = found.map(function (m) {'
            '  return JSON.parse(\'"\' + m.replace(/^pattern:\\s*"/, \'\').replace(/"$/, \'\') + \'"\');'
            '});'
            'patterns.forEach(function (p) { new RegExp(p); });'
            'console.log("compiled " + patterns.length + " patterns");'
        )
        result = subprocess.run([self._node(), "-e", script, "index.html"],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("compiled %d patterns" % len(self._embedded_patterns()),
                      result.stdout)

    def test_html_javascript_has_valid_syntax(self):
        if not self._node():
            self.skipTest("node not available")
        script = _read("index.html").split("<script>", 1)[1].split("</script>")[0]
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "snippet.js")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(script)
            result = subprocess.run([self._node(), "--check", path],
                                    capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)

    @staticmethod
    def _node():
        from shutil import which
        return which("node")

    @staticmethod
    def _embedded_patterns():
        source = _read("index.html")
        block = source.split("const RECIPES = [", 1)[1].split("\n];", 1)[0]
        return re.findall(r'pattern:\s*"((?:[^"\\]|\\.)*)"', block)


class ConstraintTests(unittest.TestCase):
    def test_source_uses_only_stdlib_imports(self):
        with open("regexlab.py", "r", encoding="utf-8") as handle:
            source = handle.read()
        imports = re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", source, re.M)
        allowed = set(sys.stdlib_module_names) | {"regexlab"}
        for module in imports:
            self.assertIn(module.split(".")[0], allowed, "non-stdlib import: %s" % module)

    def test_source_contains_no_network_or_credential_code(self):
        with open("regexlab.py", "r", encoding="utf-8") as handle:
            source = handle.read().lower()
        for banned in ("requests.", "urllib.request", "http.client", "socket.",
                       "api_key", "password =", "credential"):
            self.assertNotIn(banned, source, "banned token found: %s" % banned)


if __name__ == "__main__":
    unittest.main(verbosity=2)

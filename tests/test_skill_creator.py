"""Needs only the standard library. Run: python -m unittest discover -s tests"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "skills" / "zero1-skill-creator" / "scripts" / "skill_tool.py"


class SkillTool(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.env = {**os.environ, "USERPROFILE": str(self.home), "HOME": str(self.home), "DSH_HOME": str(self.home / ".dsh")}

    def run_tool(self, *args, stdin=""):
        return subprocess.run([sys.executable, str(TOOL), *args], input=stdin, capture_output=True, text=True, env=self.env)

    def test_new_local_writes_a_valid_skill_and_check_accepts_it(self):
        r = self.run_tool("new", "verbali", "--description", 'Usa questa skill quando serve un verbale: "formato aziendale" con azioni e scadenze.',
                          stdin="# Verbali\n\n1. Scrivi le decisioni.\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        skill = self.home / ".dsh" / "skills" / "verbali" / "SKILL.md"
        self.assertTrue(skill.exists())
        text = skill.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: verbali\ndescription: "))
        self.assertFalse((self.home / ".agents" / "skills" / "verbali").exists())
        r = self.run_tool("check", "verbali")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("ok", r.stdout)

    def test_new_global_writes_the_library_and_links_it_for_zero1code(self):
        r = self.run_tool("new", "condivisa", "--scope", "global", "--description", "Usa questa skill quando serve condividere qualcosa.", stdin="# Corpo\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        library = self.home / ".agents" / "skills" / "condivisa" / "SKILL.md"
        linked = self.home / ".dsh" / "skills" / "condivisa" / "SKILL.md"
        self.assertTrue(library.exists())
        self.assertTrue(linked.exists())                       # reachable through the link
        self.assertEqual(library.read_text(encoding="utf-8"), linked.read_text(encoding="utf-8"))

    def test_refuses_bad_names_duplicates_and_empty_input(self):
        bad = self.run_tool("new", "Nome Brutto", "--description", "Usa questa skill quando x.", stdin="corpo")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("lowercase", bad.stdout)
        ok = self.run_tool("new", "una", "--description", "Usa questa skill quando x.", stdin="corpo")
        self.assertEqual(ok.returncode, 0)
        dup = self.run_tool("new", "una", "--description", "Usa questa skill quando x.", stdin="altro")
        self.assertNotEqual(dup.returncode, 0)
        self.assertIn("already exists", dup.stderr)
        empty = self.run_tool("new", "vuota", "--description", "Usa questa skill quando x.", stdin="   ")
        self.assertNotEqual(empty.returncode, 0)
        self.assertFalse((self.home / ".dsh" / "skills" / "vuota").exists())

    def test_check_reports_errors_and_advice(self):
        folder = self.home / ".dsh" / "skills" / "rotta"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("---\nname: altro\ndescription: Aiuta.\n---\nTesto senza titoli\n", encoding="utf-8")
        r = self.run_tool("check", "rotta")
        self.assertEqual(r.returncode, 1)
        self.assertIn("must equal the folder name", r.stdout)
        self.assertIn("WHEN", r.stdout)
        self.assertIn("headings", r.stdout)


if __name__ == "__main__":
    unittest.main()

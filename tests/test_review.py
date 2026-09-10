import unittest

from hydra.review import files_in_diff, review_diff
from hydra.tasks import Task

DIFF_OK = """diff --git a/src/slug.py b/src/slug.py
new file mode 100644
--- /dev/null
+++ b/src/slug.py
@@ -0,0 +1,2 @@
+def slugify(s):
+    return s.lower()
"""

DIFF_SCOPE_BREACH = """diff --git a/src/slug.py b/src/slug.py
--- a/src/slug.py
+++ b/src/slug.py
@@ -1 +1 @@
-x
+y
diff --git a/src/other.py b/src/other.py
--- a/src/other.py
+++ b/src/other.py
@@ -1 +1 @@
-a
+b
"""

DIFF_SECRET = """diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -0,0 +1 @@
+api_key = "AKIAIOSFODNN7EXAMPLE1"
"""


def T(files):
    return Task(id="t", title="t", prompt="p", files=tuple(files))


class ReviewTest(unittest.TestCase):
    def test_files_in_diff(self):
        self.assertEqual(files_in_diff(DIFF_SCOPE_BREACH), ["src/slug.py", "src/other.py"])

    def test_clean_diff_passes(self):
        r = review_diff(T(["src/slug.py"]), DIFF_OK)
        self.assertTrue(r.passed, r.findings)

    def test_empty_diff_fails(self):
        self.assertFalse(review_diff(T(["x"]), "").passed)

    def test_scope_breach_when_another_task_owns_the_file(self):
        r = review_diff(T(["src/slug.py"]), DIFF_SCOPE_BREACH,
                        other_task_files={"src/other.py"})
        self.assertFalse(r.passed)
        self.assertTrue(any("scope breach" in f for f in r.findings))

    def test_undeclared_file_no_one_owns_is_allowed(self):
        # touches src/other.py, which no other task declares -> fine (shared infra)
        r = review_diff(T(["src/slug.py"]), DIFF_SCOPE_BREACH, other_task_files=set())
        self.assertTrue(r.passed, r.findings)

    def test_declared_dir_glob_allows(self):
        r = review_diff(T(["src/**"]), DIFF_SCOPE_BREACH,
                        other_task_files={"src/other.py"})
        self.assertTrue(r.passed, r.findings)

    def test_secret_flagged(self):
        r = review_diff(T(["config.py"]), DIFF_SECRET)
        self.assertFalse(r.passed)
        self.assertTrue(any("secret" in f for f in r.findings))


if __name__ == "__main__":
    unittest.main()

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MigrationChainTests(unittest.TestCase):
    def revisions(self):
        revisions = {}
        for path in (ROOT / "migrations" / "versions").glob("*.py"):
            values = {}
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if (
                    isinstance(node, ast.AnnAssign)
                    and isinstance(node.target, ast.Name)
                    and node.target.id in {"revision", "down_revision"}
                ):
                    values[node.target.id] = ast.literal_eval(node.value)
            if "revision" in values:
                revisions[values["revision"]] = values.get("down_revision")
        return revisions

    def test_revisions_form_one_chain_through_0015(self):
        revisions = self.revisions()

        current = "0015_evidence_review"
        seen = []
        while current is not None:
            self.assertNotIn(current, seen)
            self.assertIn(current, revisions)
            seen.append(current)
            current = revisions[current]

        self.assertEqual(len(seen), 15)
        self.assertEqual(seen[-1], "0001_core_schema")

    def test_latest_revision_is_single_0028_head(self):
        revisions = self.revisions()
        heads = set(revisions) - {x for x in revisions.values() if x is not None}
        self.assertEqual(heads, {"0028_player_relationships"})


if __name__ == "__main__":
    unittest.main()

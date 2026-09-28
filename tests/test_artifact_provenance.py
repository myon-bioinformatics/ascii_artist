import ast
from datetime import datetime
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "ascii_artist.py"
HEADER_RE = re.compile(
    r"^# metadata: __all__=(?P<count>[0-9]+) \| "
    r"base_sha=(?P<sha>(?:[0-9a-f]{40}|[0-9a-f]{64})) \| "
    r"updated_at=(?P<updated_at>\S+)$"
)


class ArtifactProvenanceTests(unittest.TestCase):
    def test_header_matches_literal_all(self):
        source = ARTIFACT.read_text(encoding="utf-8")
        header = next(
            (line for line in source.splitlines()[:8] if line.startswith("# metadata:")),
            None,
        )
        self.assertIsNotNone(header)
        match = HEADER_RE.fullmatch(header or "")
        self.assertIsNotNone(match)

        tree = ast.parse(source)
        all_values = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                all_values.append(ast.literal_eval(node.value))

        self.assertEqual(len(all_values), 1)
        self.assertIsInstance(all_values[0], list)
        self.assertTrue(all(isinstance(item, str) for item in all_values[0]))
        self.assertEqual(int(match.group("count")), len(all_values[0]))

        updated = datetime.fromisoformat(
            match.group("updated_at").replace("Z", "+00:00")
        )
        self.assertIsNotNone(updated.tzinfo)


if __name__ == "__main__":
    unittest.main()

# test_ascii_artist.py
# __all__: 0

__all__ = []

import unittest
from types import SimpleNamespace

import ascii_artist


class _LightGenerator:
    def generate_light(self, prompt: str):
        return SimpleNamespace(text="assistant\n```ascii\n /\\_/\\\n( o.o )\n```\n")


class AsciiArtistTests(unittest.TestCase):
    def test_generate_square(self):
        self.assertEqual(ascii_artist.generate_square(2), "**\n**")

    def test_generate_triangle(self):
        self.assertEqual(ascii_artist.generate_triangle(3), "*\n**\n***")

    def test_generate_diamond(self):
        self.assertEqual(ascii_artist.generate_diamond(2), " *\n***\n *")

    def test_non_positive_sizes_return_empty(self):
        self.assertEqual(ascii_artist.generate_square(0), "")
        self.assertEqual(ascii_artist.generate_triangle(-1), "")
        self.assertEqual(ascii_artist.generate_diamond(0), "")

    def test_unicode_token_is_repeated_as_token_not_display_cells(self):
        self.assertEqual(ascii_artist.generate_square(2, "☺️"), "☺️☺️\n☺️☺️")

    def test_empty_or_multiline_token_is_rejected(self):
        with self.assertRaises(ValueError):
            ascii_artist.generate_square(2, "")
        with self.assertRaises(ValueError):
            ascii_artist.generate_square(2, "x\ny")
        with self.assertRaises(TypeError):
            ascii_artist.generate_square(2, 1)

    def test_templates_are_case_insensitive_and_include_generic_entries(self):
        self.assertEqual(ascii_artist.get_template("CAT"), ascii_artist.get_template("cat"))
        self.assertIn("cat", ascii_artist.list_templates())
        self.assertIn("heart", ascii_artist.list_templates())
        self.assertEqual(ascii_artist.get_template("missing"), "")

    def test_render_accepts_generate_light_object_and_sanitizes_wrappers(self):
        self.assertEqual(
            ascii_artist.render_prompt_ascii("cat", _LightGenerator()),
            " /\\_/\\\n( o.o )",
        )

    def test_render_accepts_plain_callable_returning_string(self):
        def generate(_prompt: str) -> str:
            return "[assistant]:\r\nHere is your ASCII art:\r\n~~~text\r\n<*>\r\n~~~\r\n"

        self.assertEqual(ascii_artist.render_prompt_ascii("star", generate), "<*>")

    def test_render_accepts_callable_result_with_text_attribute(self):
        def generate(_prompt: str):
            return SimpleNamespace(text="ASCII art:\n```\n[]\n```")

        self.assertEqual(ascii_artist.render_prompt_ascii("box", generate), "[]")


    def test_capability_stance_is_exposed(self):
        self.assertIn("generation", ascii_artist.SUPPORTED)
        self.assertIn("layout", ascii_artist.UNSUPPORTED)
        self.assertIn(
            "terminal-cell-perfect alignment for wide Unicode or emoji",
            ascii_artist.UNSUPPORTED["layout"],
        )


    def test_diagram_dict_round_trip_is_lossless(self):
        original = ascii_artist.diagram(
            [
                ascii_artist.Node("llm", "LLM"),
                ascii_artist.Node("mcp", "MCP"),
                ascii_artist.Node("python", "Python"),
            ],
            [("llm", "mcp"), ("mcp", "python")],
        )
        self.assertEqual(ascii_artist.from_dict(ascii_artist.to_dict(original)), original)

    def test_diagram_rejects_cycles_and_unknown_endpoints(self):
        with self.assertRaises(ValueError):
            ascii_artist.diagram(["a", "b"], [("a", "b"), ("b", "a")])
        with self.assertRaises(ValueError):
            ascii_artist.diagram(["a"], [("a", "missing")])

    def test_flow_unicode_and_ascii(self):
        self.assertEqual(
            ascii_artist.flow(["LLM", "MCP", "Python"]),
            "LLM\n ↓\nMCP\n ↓\nPython",
        )
        self.assertEqual(
            ascii_artist.flow(["LLM", "MCP"], charset="ascii"),
            "LLM\n v\nMCP",
        )

    def test_branch_renders_one_to_many_to_one(self):
        rendered = ascii_artist.branch(
            "Python API",
            ["RCON", "Paper bridge", "mcpi"],
            "Minecraft",
        )
        self.assertIn("Python API", rendered)
        self.assertIn("RCON", rendered)
        self.assertIn("Paper bridge", rendered)
        self.assertIn("mcpi", rendered)
        self.assertIn("Minecraft", rendered)
        self.assertIn("┼", rendered)

    def test_tree_renders_nested_mapping(self):
        rendered = ascii_artist.tree(
            "LLM",
            {
                "MCP": {
                    "Python": {
                        "Minecraft Adapter": {},
                    }
                }
            },
        )
        self.assertEqual(
            rendered,
            "LLM\n└─→ MCP\n   └─→ Python\n      └─→ Minecraft Adapter",
        )

    def test_generic_dag_renderer_preserves_all_edges(self):
        value = ascii_artist.diagram(
            ["api", "rcon", "paper", "mcpi", "minecraft"],
            [
                ("api", "rcon"),
                ("api", "paper"),
                ("api", "mcpi"),
                ("rcon", "minecraft"),
                ("paper", "minecraft"),
                ("mcpi", "minecraft"),
            ],
        )
        rendered = ascii_artist.render_diagram(value)
        self.assertIn("├─→ rcon", rendered)
        self.assertIn("├─→ paper", rendered)
        self.assertIn("└─→ mcpi", rendered)
        self.assertEqual(rendered.count("└─→ minecraft"), 3)


    def test_tree_handles_very_deep_nesting_iteratively(self):
        children = {}
        current = children
        for index in range(1200):
            next_level = {}
            current[f"n{index}"] = next_level
            current = next_level
        rendered = ascii_artist.tree("root", children)
        self.assertIn("n1199", rendered)

    def test_from_dict_reports_specific_bad_fields(self):
        with self.assertRaisesRegex(TypeError, "node id must be str"):
            ascii_artist.from_dict({"nodes": [{"id": 1, "label": "x"}], "edges": []})
        with self.assertRaisesRegex(TypeError, "node 'x' label must be str"):
            ascii_artist.from_dict({"nodes": [{"id": "x", "label": 1}], "edges": []})
        with self.assertRaisesRegex(TypeError, "edge source must be str"):
            ascii_artist.from_dict({
                "nodes": [{"id": "x", "label": "x"}],
                "edges": [{"source": 1, "target": "x"}],
            })

    def test_render_rejects_invalid_generator_result(self):
        with self.assertRaises(TypeError):
            ascii_artist.render_prompt_ascii("x", lambda _prompt: 123)


if __name__ == "__main__":
    unittest.main()

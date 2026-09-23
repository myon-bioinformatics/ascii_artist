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


    def test_json_round_trip_is_lossless(self):
        original = ascii_artist.diagram(
            [
                ascii_artist.Node("llm", "LLM"),
                ascii_artist.Node("mcp", "MCP"),
                ascii_artist.Node("日本語", '日本語 "node"'),
            ],
            [("llm", "mcp"), ("mcp", "日本語")],
        )
        self.assertEqual(ascii_artist.from_json(ascii_artist.to_json(original)), original)

    def test_edges_and_adjacency_adapters(self):
        original = ascii_artist.diagram(
            [
                ascii_artist.Node("a", "A"),
                ascii_artist.Node("b", "B"),
                ascii_artist.Node("c", "C"),
            ],
            [("a", "b"), ("a", "c")],
        )
        self.assertEqual(ascii_artist.to_edges(original), [("a", "b"), ("a", "c")])
        rebuilt = ascii_artist.from_edges(
            ascii_artist.to_edges(original),
            labels={"a": "A", "b": "B", "c": "C"},
        )
        self.assertEqual(rebuilt, original)
        adjacency = ascii_artist.to_adjacency(original)
        self.assertEqual(adjacency, {"a": ["b", "c"], "b": [], "c": []})
        self.assertEqual(
            ascii_artist.from_adjacency(
                adjacency,
                labels={"a": "A", "b": "B", "c": "C"},
            ),
            original,
        )

    def test_mermaid_round_trip_normalizes_supported_subset(self):
        original = ascii_artist.diagram(
            [
                ascii_artist.Node("a", 'A "quoted"'),
                ascii_artist.Node("b", "日本語"),
            ],
            [("a", "b")],
        )
        rendered = ascii_artist.to_mermaid(original)
        self.assertTrue(rendered.startswith("flowchart TD"))
        self.assertEqual(ascii_artist.from_mermaid(rendered), original)

    def test_dot_round_trip_normalizes_supported_subset(self):
        original = ascii_artist.diagram(
            [
                ascii_artist.Node("a", 'A "quoted"'),
                ascii_artist.Node("b", "日本語"),
            ],
            [("a", "b")],
        )
        rendered = ascii_artist.to_dot(original)
        self.assertTrue(rendered.startswith("digraph G {"))
        self.assertEqual(ascii_artist.from_dot(rendered), original)

    def test_markdown_outline_subset(self):
        outline = "# Root\n## Child A\n### Leaf\n## Child B"
        value = ascii_artist.from_markdown_outline(outline)
        self.assertEqual(
            [node.label for node in value.nodes],
            ["Root", "Child A", "Leaf", "Child B"],
        )
        self.assertEqual(
            ascii_artist.to_edges(value),
            [("n0", "n1"), ("n1", "n2"), ("n0", "n3")],
        )
        rendered = ascii_artist.to_markdown_outline(value)
        self.assertIn("# Root", rendered)
        self.assertIn("## Child A", rendered)

    def test_inventory_reports_roots_leaves_layers_and_depth(self):
        value = ascii_artist.diagram(
            ["a", "b", "c", "d"],
            [("a", "b"), ("a", "c"), ("c", "d")],
        )
        report = ascii_artist.inventory(value)
        self.assertEqual(report["nodes"], 4)
        self.assertEqual(report["edges"], 3)
        self.assertEqual(report["roots"], ["a"])
        self.assertEqual(report["leaves"], ["b", "d"])
        self.assertEqual(report["layers"], [["a"], ["b", "c"], ["d"]])
        self.assertEqual(report["max_depth"], 3)
        self.assertTrue(report["is_dag"])

    def test_subset_parsers_reject_unsupported_lines(self):
        with self.assertRaises(ValueError):
            ascii_artist.from_mermaid("flowchart TD\n    a ==> b")
        with self.assertRaises(ValueError):
            ascii_artist.from_dot("digraph G {\n  a -- b;\n}")
        with self.assertRaises(ValueError):
            ascii_artist.from_markdown_outline("# ok\nplain prose")

    def test_render_rejects_invalid_generator_result(self):
        with self.assertRaises(TypeError):
            ascii_artist.render_prompt_ascii("x", lambda _prompt: 123)


if __name__ == "__main__":
    unittest.main()


    def test_to_web_ui_v1_html_escapes_text_and_uses_contract(self):
        rendered = ascii_artist.to_web_ui_v1_html(
            "<box> & text",
            title="ASCII <demo>",
            theme="github-like",
        )
        self.assertIn('<body data-ui-theme="github-like">', rendered)
        self.assertIn('<main class="ui-page">', rendered)
        self.assertIn('<h1 class="ui-title">ASCII &lt;demo&gt;</h1>', rendered)
        self.assertIn('<section class="ui-panel">', rendered)
        self.assertIn('<pre class="ui-output">&lt;box&gt; &amp; text</pre>', rendered)

    def test_to_web_ui_v1_html_accepts_diagram(self):
        value = ascii_artist.diagram(["A", "B"], [("A", "B")])
        rendered = ascii_artist.to_web_ui_v1_html(value)
        self.assertIn("A", rendered)
        self.assertIn("B", rendered)
        self.assertIn("ui-output", rendered)

    def test_to_web_ui_v1_html_rejects_unknown_theme(self):
        with self.assertRaises(ValueError):
            ascii_artist.to_web_ui_v1_html("x", theme="unknown")

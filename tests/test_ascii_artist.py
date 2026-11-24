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

    def test_generate_box_single_line(self):
        expected = "┌───────┐\n│ Hello │\n└───────┘"
        self.assertEqual(ascii_artist.generate_box("Hello"), expected)

    def test_generate_box_styles(self):
        self.assertEqual(
            ascii_artist.generate_box("Hi", padding=0, style="single"),
            "┌──┐\n│Hi│\n└──┘",
        )
        self.assertEqual(
            ascii_artist.generate_box("Hi", padding=0, style="double"),
            "╔══╗\n║Hi║\n╚══╝",
        )
        self.assertEqual(
            ascii_artist.generate_box("Hi", padding=0, style="rounded"),
            "╭──╮\n│Hi│\n╰──╯",
        )
        self.assertEqual(
            ascii_artist.generate_box("Hi", padding=0, style="ascii"),
            "+--+\n|Hi|\n+--+",
        )

    def test_generate_box_counts_wide_and_combining_characters_by_cell(self):
        self.assertEqual(ascii_artist.display_width("日本"), 4)
        self.assertEqual(ascii_artist.display_width("e\u0301"), 1)
        self.assertEqual(
            ascii_artist.generate_box("日本\nab", padding=0, style="ascii"),
            "+----+\n|日本|\n|ab  |\n+----+",
        )
        self.assertEqual(
            ascii_artist.generate_box("e\u0301x", padding=0, style="ascii"),
            "+--+\n|e\u0301x|\n+--+",
        )

    def test_generate_box_unhashable_style_is_value_error(self):
        with self.assertRaises(ValueError):
            ascii_artist.generate_box("x", style=["single"])

    def test_generate_box_multiline_and_padding(self):
        text = "Hello\nWorld!"
        expected = "┌──────────┐\n│  Hello   │\n│  World!  │\n└──────────┘"
        self.assertEqual(ascii_artist.generate_box(text, padding=2), expected)

    def test_generate_box_validation(self):
        with self.assertRaises(TypeError):
            ascii_artist.generate_box(123)
        with self.assertRaises(ValueError):
            ascii_artist.generate_box("text", padding=-1)
        with self.assertRaises(ValueError):
            ascii_artist.generate_box("text", padding=True)
        with self.assertRaises(ValueError):
            ascii_artist.generate_box("text", style="invalid")

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

    def test_generic_templates_are_plain_ascii_without_brand(self):
        names = ascii_artist.list_templates()
        for name in ("coffee", "dog", "fish", "owl", "rocket", "star"):
            self.assertIn(name, names)
            art = ascii_artist.get_template(name)
            self.assertTrue(art.endswith("\n"))
            self.assertTrue(art.isascii())
            self.assertNotIn("IRONMATE", art.upper())
        self.assertEqual(names, sorted(names))

    def test_banner_font_glyphs_are_rectangular_and_cover_charset(self):
        charset = ascii_artist.banner_charset()
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !?.,:'-_+=/()":
            self.assertIn(ch, charset)
        for ch, rows in ascii_artist._BANNER_FONT.items():
            self.assertEqual(len(rows), 5, ch)
            self.assertEqual(len({len(row) for row in rows}), 1, ch)
            self.assertLessEqual(set("".join(rows)), {"#", " "}, ch)

    def test_banner_renders_exact_rows(self):
        self.assertEqual(
            ascii_artist.banner("HI"),
            "#   # ###\n#   #  #\n#####  #\n#   #  #\n#   # ###",
        )
        self.assertEqual(ascii_artist.banner("I", char="%"), "%%%\n %\n %\n %\n%%%")
        self.assertEqual(ascii_artist.banner("II", spacing=0).splitlines()[0], "######")
        self.assertEqual(ascii_artist.banner(""), "")

    def test_banner_lowercase_folds_to_uppercase(self):
        self.assertEqual(ascii_artist.banner("abc xyz"), ascii_artist.banner("ABC XYZ"))

    def test_banner_wide_token_pads_blank_cells(self):
        rows = ascii_artist.banner("I", char="漢").splitlines()
        self.assertEqual(rows[1], "  漢")
        self.assertEqual(ascii_artist.display_width(rows[0]), 6)

    def test_banner_unsupported_characters_error_or_fallback(self):
        with self.assertRaisesRegex(ValueError, r"unsupported banner characters: 'é', '\*'"):
            ascii_artist.banner("éé*")
        self.assertEqual(ascii_artist.banner("é", fallback="?"), ascii_artist.banner("?"))
        self.assertEqual(ascii_artist.banner("é", fallback="x"), ascii_artist.banner("X"))
        for bad in ("", "??", "*", 1):
            with self.assertRaises(ValueError):
                ascii_artist.banner("A", fallback=bad)

    def test_banner_rejects_invalid_arguments(self):
        with self.assertRaises(TypeError):
            ascii_artist.banner(1)
        with self.assertRaises(ValueError):
            ascii_artist.banner("A\nB")
        with self.assertRaises(ValueError):
            ascii_artist.banner("A", char="")
        for spacing in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                ascii_artist.banner("A", spacing=spacing)

    def test_render_table_ascii_with_headers_and_alignment(self):
        self.assertEqual(
            ascii_artist.render_table([["apple", 120], ["kiwi", 3]], headers=["name", "yen"], align="lr"),
            "+-------+-----+\n"
            "| name  | yen |\n"
            "+-------+-----+\n"
            "| apple | 120 |\n"
            "| kiwi  |   3 |\n"
            "+-------+-----+",
        )

    def test_render_table_cjk_width_and_center(self):
        rendered = ascii_artist.render_table([["りんご", "x"]], headers=["名前", "c"], align=["center", "c"])
        lines = rendered.splitlines()
        self.assertEqual(lines[1], "|  名前  | c |")
        self.assertEqual(lines[3], "| りんご | x |")
        self.assertEqual({ascii_artist.display_width(line) for line in lines}, {14})

    def test_render_table_styles_ragged_rows_and_none(self):
        self.assertEqual(
            ascii_artist.render_table([["a", None], ["b"]], style="single", padding=0),
            "┌─┬┐\n│a││\n│b││\n└─┴┘",
        )
        self.assertEqual(
            ascii_artist.render_table([], headers=["h"], style="double"),
            "╔═══╗\n║ h ║\n╠═══╣\n╚═══╝",
        )
        self.assertTrue(ascii_artist.render_table([["x"]], style="rounded").startswith("╭"))
        self.assertEqual(ascii_artist.render_table([]), "")
        self.assertEqual(ascii_artist.render_table([[]]), "")

    def test_render_table_rejects_invalid_input(self):
        cases = [
            (ValueError, ([["a\nb"]],), {}),
            (ValueError, ([["a"]],), {"style": "fancy"}),
            (ValueError, ([["a"]],), {"padding": -1}),
            (ValueError, ([["a"]],), {"padding": True}),
            (ValueError, ([["a"]],), {"align": "lr"}),
            (ValueError, ([["a"]],), {"align": "x"}),
            (ValueError, ([["a"]],), {"align": [1]}),
            (TypeError, ("ab",), {}),
            (TypeError, (["ab"],), {}),
            (TypeError, ([["a"]],), {"headers": "h"}),
        ]
        for exc, args, kwargs in cases:
            with self.assertRaises(exc, msg=(args, kwargs)):
                ascii_artist.render_table(*args, **kwargs)

    def test_new_capabilities_are_in_stance(self):
        joined = " ".join(ascii_artist.SUPPORTED["generation"])
        self.assertIn("banner font", joined)
        self.assertIn("tables", joined)
        self.assertIn("ANSI color rendering", ascii_artist.UNSUPPORTED["rendering"])
        self.assertIn("image/raster rendering or image decoding", ascii_artist.UNSUPPORTED["rendering"])

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

    def test_to_web_ui_v1_html_empty_diagram(self):
        rendered = ascii_artist.to_web_ui_v1_html(ascii_artist.diagram([], []))
        self.assertIn('<pre class="ui-output"></pre>', rendered)

    def test_to_web_ui_v1_html_preserves_multiline_text_after_escape(self):
        rendered = ascii_artist.to_web_ui_v1_html("<a>\n&b")
        self.assertIn('&lt;a&gt;\n&amp;b', rendered)

    def test_to_web_ui_v1_html_rejects_unknown_charset_for_diagram(self):
        with self.assertRaises(ValueError):
            ascii_artist.to_web_ui_v1_html(
                ascii_artist.diagram(["A"], []),
                charset="cp437",
            )


if __name__ == "__main__":
    unittest.main()

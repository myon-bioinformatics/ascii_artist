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

    def test_render_rejects_invalid_generator_result(self):
        with self.assertRaises(TypeError):
            ascii_artist.render_prompt_ascii("x", lambda _prompt: 123)


if __name__ == "__main__":
    unittest.main()

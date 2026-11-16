import io
import unittest
import curses
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from characters import normalize_characters
from config import CHARSETS
from languages import TEXT
from main import draw, initialize_colors, main, parse_arguments
from test_lesson import Screen
from trainer import Generator, Lesson


class LanguageTests(unittest.TestCase):
    def test_target_colors_can_be_set_from_command_line(self):
        defaults = parse_arguments([])
        self.assertEqual((defaults.target_fg, defaults.target_bg), ("black", "white"))
        custom = parse_arguments(["--target-fg", "blue", "--target-bg", "yellow"])
        self.assertEqual((custom.target_fg, custom.target_bg), ("blue", "yellow"))

    @patch("main.curses.has_colors", return_value=True)
    @patch("main.curses.start_color")
    @patch("main.curses.init_pair")
    @patch("main.curses.color_pair", side_effect=lambda pair: pair << 8)
    def test_target_palette_uses_selected_foreground_and_background(self, _, init_pair, *__):
        self.assertEqual(initialize_colors("blue", "yellow"), 4 << 8)
        init_pair.assert_any_call(4, curses.COLOR_BLUE, curses.COLOR_YELLOW)
        init_pair.assert_any_call(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    @patch("main.curses.color_pair", side_effect=lambda pair: pair)
    def test_target_background_fills_row_and_survives_shorter_word(self, _):
        lesson = Lesson(2, 2, Generator("я"))
        screen = Screen()
        styles = 1234
        draw(screen, lesson, None, target_style=styles)
        self.assertIn((6, 0, " " * 79, 1234), screen.output)
        self.assertIn((6, 7, "я", 1234 | curses.A_UNDERLINE), screen.output)
        self.assertIn((6, 8, "я", 1234), screen.output)
        lesson.type_char("я", 0)
        draw(screen, lesson, None, target_style=styles)
        self.assertIn((6, 0, " " * 79, 1234), screen.output)
        self.assertIn((6, 7, "я", 1234), screen.output)
        self.assertIn((6, 8, "я", 1234 | curses.A_UNDERLINE), screen.output)

    def test_interface_and_practice_set_are_independent(self):
        self.assertEqual(parse_arguments([]).language, "en")
        args = parse_arguments(["--language", "en", "--charset", "ru", "--word-length", "5"])
        self.assertEqual((args.language, args.charset, args.word_length), ("en", "ru", 5))
        for name, characters in CHARSETS.items():
            generator = Generator(characters)
            self.assertEqual(set(generator.weights), set(characters), name)
            self.assertTrue(set(generator.next_sequence(200)) <= set(characters))

    def test_custom_characters_normalize_and_reject_unsupported_input(self):
        args = parse_arguments(["--chars", "a\u0304āбб"])
        self.assertEqual(args.chars, "āб")
        for invalid in ("", "\t", "a\n", "\u0304", "界", "🙂"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_characters(invalid)

    def test_pending_set_is_retained_when_current_word_ends_lesson(self):
        lesson = Lesson(3, 3, Generator("a"))
        lesson.type_char("a", 0)
        lesson.set_characters("яā")
        lesson.type_char("a", 1)
        lesson.type_char("a", 2)
        self.assertTrue(lesson.complete)
        self.assertEqual(lesson.stats.total_hits, 3)
        next_lesson = Lesson(3, 3, lesson.generator)
        self.assertTrue(set(next_lesson.target) <= set("яā"))
        self.assertEqual(set(next_lesson.generator.weights), set("яā"))

    def test_help_and_validation_use_selected_language(self):
        for language in TEXT:
            with self.subTest(language=language):
                output = io.StringIO()
                with redirect_stdout(output), self.assertRaises(SystemExit) as result:
                    parse_arguments(["--help", "--language", language])
                self.assertEqual(result.exception.code, 0)
                self.assertIn(TEXT[language]["description"], output.getvalue())
                for option, value, message in (
                    ("--word-length", "0", "positive"),
                    ("--lesson-length", "abc", "positive"),
                    ("--chars", "", "invalid_chars"),
                ):
                    output = io.StringIO()
                    with redirect_stderr(output), self.assertRaises(SystemExit) as result:
                        parse_arguments(["--language", language, option, value])
                    self.assertEqual(result.exception.code, 2)
                    self.assertIn(TEXT[language][message], output.getvalue())

    @patch("main.curses.color_pair", side_effect=lambda pair: pair)
    def test_unicode_history_and_results_render_in_all_languages(self, _):
        lesson = Lesson(2, 1, Generator("я"))
        lesson.type_char("я", 1)
        lesson.type_char("ā", 2)
        for language in TEXT:
            screen = Screen()
            draw(screen, lesson, None, language, "ru")
            self.assertIn((11, 2, "я", 1), screen.output)
            self.assertIn((11, 3, "я", 2), screen.output)
            self.assertIn((11, 4, "ā", 3 | curses.A_BOLD), screen.output)
            self.assertIn((0, 2, TEXT[language]["complete"], 0), screen.output)

    @patch("main.curses.curs_set")
    @patch("main.curses.has_colors", return_value=False)
    @patch("trainer.random.choices", side_effect=lambda population, weights, k: [population[0]] * k)
    @patch("main.draw", return_value=0)
    def test_switching_preserves_word_history_and_settings_on_restart(self, draw_mock, *_):
        snapshots = []

        def capture(screen, lesson, scroll, language, charset, target_style=None):
            snapshots.append((lesson, lesson.target, lesson.position,
                              lesson.pending_characters, language, charset, len(lesson.history)))
            return 0

        draw_mock.side_effect = capture
        screen = Screen(keys=["a", curses.KEY_F4, "a", "а", curses.KEY_F3,
                              "а", "\n", "\x1b"])
        main(screen, lesson_length=4, word_length=2, language="ru")
        pending = snapshots[2]
        self.assertEqual((pending[1], pending[2], pending[3], pending[5]),
                         ("aa", 1, CHARSETS["ru"], "ru"))
        self.assertEqual(snapshots[3][1], "аа")
        finished = snapshots[-2][0]
        self.assertEqual(finished.stats.total_hits, 4)
        self.assertEqual(finished.stats.total_errors, 0)
        self.assertEqual(snapshots[-1][4:7], ("en", "ru", 0))
        self.assertIsNone(snapshots[-1][0].started_at)

    @patch("main.curses.curs_set")
    @patch("main.curses.has_colors", return_value=False)
    @patch("main.draw", return_value=0)
    def test_custom_set_remains_available_when_cycling_presets(self, draw_mock, *_):
        screen = Screen(keys=[curses.KEY_F4] * (len(CHARSETS) + 1) + ["\x1b"])
        main(screen, characters="ёā")
        lesson = draw_mock.call_args.args[1]
        self.assertEqual(set(lesson.generator.weights), set("ёā"))
        self.assertEqual(draw_mock.call_args.args[4], "custom")
        self.assertIsNone(lesson.started_at)


if __name__ == "__main__":
    unittest.main()

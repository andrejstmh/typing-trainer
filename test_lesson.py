import curses
import unittest
from unittest.mock import patch

from main import draw, main
from trainer import Generator, Lesson


class FixedGenerator:
    def next_sequence(self, length):
        return ("abc" * length)[:length]

    def adapt(self, char, interval):
        pass


class Screen:
    def __init__(self, height=24, width=80, keys=()):
        self.height, self.width = height, width
        self.keys = iter(keys)
        self.output = []

    def getmaxyx(self):
        return self.height, self.width

    def erase(self):
        self.output = []

    def addstr(self, row, col, text, attr):
        assert 0 <= row < self.height
        assert 0 <= col and col + len(text) < self.width
        self.output.append((row, col, text, attr))

    def refresh(self):
        pass

    def keypad(self, enabled):
        pass

    def timeout(self, value):
        pass

    def get_wch(self):
        return next(self.keys)


class GeneratorTests(unittest.TestCase):
    def test_slow_character_cannot_dominate_after_many_lessons(self):
        generator = Generator()
        for _ in range(1000):
            for char in generator.weights:
                generator.adapt(char, 1.0 if char == "b" else 0.1)
        probability = generator.weights["b"] / sum(generator.weights.values())
        self.assertGreater(probability, 1 / len(generator.weights))
        self.assertLess(probability, 0.1)
        self.assertTrue(all(weight > 0 for weight in generator.weights.values()))

    def test_weight_can_decrease_after_slow_typing_and_increase_after_fast_typing(self):
        generator = Generator()
        for _ in range(1000):
            generator.adapt("b", 1.0)
            generator.adapt("a", 0.1)
        slow_weight = generator.weights["b"]
        fast_weight = generator.weights["a"]
        generator.adapt("b", 0.1)
        generator.adapt("a", 1.0)
        self.assertLess(generator.weights["b"], slow_weight)
        self.assertGreater(generator.weights["a"], fast_weight)


class LessonTests(unittest.TestCase):
    def test_timer_starts_on_first_character_and_freezes_on_completion(self):
        lesson = Lesson(2, 1, FixedGenerator())
        self.assertEqual(lesson.elapsed(100), 0)
        lesson.type_char("x", 100)
        self.assertEqual(lesson.started_at, 100)
        self.assertEqual(lesson.elapsed(100), 0)
        self.assertEqual(lesson.elapsed(102), 2)
        lesson.type_char("a", 103)
        self.assertEqual(lesson.elapsed(200), 3)

    def test_counts_each_character_and_stops_exactly_at_limit(self):
        lesson = Lesson(5, 3, FixedGenerator())
        lesson.start(0)
        for now, char in enumerate("axcab", 1):
            lesson.type_char(char, now)
        self.assertTrue(lesson.complete)
        self.assertEqual(lesson.remaining, 0)
        self.assertEqual(lesson.stats.total_hits, 4)
        self.assertEqual(lesson.stats.total_errors, 1)
        self.assertEqual([entry.char for entry in lesson.history], list("axcab"))
        self.assertEqual([entry.expected for entry in lesson.history], list("abcab"))
        self.assertEqual([entry.correct for entry in lesson.history], [True, False, True, True, True])
        self.assertNotIn("a->c", lesson.stats.transition_stats)
        lesson.type_char("x", 100)
        self.assertEqual(len(lesson.history), 5)
        self.assertEqual(lesson.elapsed(100), 5)

    def test_sequence_length_change_preserves_current_input(self):
        lesson = Lesson(4, 3, FixedGenerator())
        lesson.type_char("a", 1)
        lesson.set_sequence_length(1)
        lesson.type_char("b", 2)
        lesson.type_char("c", 3)
        self.assertEqual(lesson.target, "a")
        self.assertEqual(lesson.remaining, 1)

    def test_word_length_changes_immediately_before_typing_and_respects_limits(self):
        lesson = Lesson(5, 1, FixedGenerator())
        lesson.set_sequence_length(3)
        self.assertEqual(lesson.target, "abc")
        self.assertIsNone(lesson.started_at)
        lesson.set_sequence_length(0)
        self.assertEqual(lesson.target, "a")
        lesson.set_sequence_length(100)
        self.assertEqual(lesson.sequence_length, 5)
        self.assertEqual(len(lesson.target), 5)

    @patch("main.curses.color_pair", side_effect=lambda pair: pair)
    def test_only_latest_mistake_is_shown_below_clean_target(self, _):
        lesson = Lesson(6, 3, FixedGenerator())
        screen = Screen()
        styles = 4
        lesson.type_char("a", 0)
        lesson.type_char("x", 1)
        draw(screen, lesson, None, language="en", target_style=styles)
        self.assertEqual([(col, chars) for row, col, chars, _ in screen.output
                          if row == 6 and chars.strip()], [(7, "ab"), (9, "c")])
        self.assertEqual([entry for entry in screen.output if entry[0] == 7], [(7, 7, "b→x", 3 | curses.A_BOLD)])

        lesson.type_char(" ", 2)
        draw(screen, lesson, None, language="en", target_style=styles)
        self.assertIn((6, 7, "a", 4 | curses.A_UNDERLINE), screen.output)
        self.assertEqual([entry for entry in screen.output if entry[0] == 7], [(7, 7, "c→␣", 3 | curses.A_BOLD)])

        lesson.type_char("a", 3)
        draw(screen, lesson, None, language="en", target_style=styles)
        self.assertIn((6, 7, "a", 4), screen.output)
        self.assertFalse(any(row == 7 for row, _, _, _ in screen.output))

        lesson.type_char("b", 4)
        lesson.type_char("x", 5)
        draw(screen, lesson, None, language="en", target_style=styles)
        self.assertFalse(any(row == 6 for row, _, _, _ in screen.output))
        self.assertIn((7, 7, "c→x", 3 | curses.A_BOLD), screen.output)

    @patch("main.curses.color_pair", side_effect=lambda pair: pair)
    def test_history_wraps_scrolls_and_uses_requested_colors(self, _):
        lesson = Lesson(200, 1, FixedGenerator())
        for now in range(200):
            lesson.type_char("a" if now % 2 == 0 else "x", now)
        screen = Screen(16, 40)
        self.assertEqual(draw(screen, lesson, None), 7)
        self.assertEqual(draw(screen, lesson, 0), 0)
        self.assertIn((11, 2, "a", 1), screen.output)
        self.assertIn((11, 3, "a", 2), screen.output)
        self.assertIn((11, 4, "x", 3 | curses.A_BOLD), screen.output)
        self.assertEqual(draw(Screen(8, 20), lesson, None), 0)

    @patch("main.curses.color_pair", side_effect=lambda pair: pair)
    def test_error_pair_wraps_without_changing_lesson_count(self, _):
        lesson = Lesson(36, 1, FixedGenerator())
        for now in range(35):
            lesson.type_char("a", now)
        lesson.type_char("x", 35)
        screen = Screen(16, 40)
        draw(screen, lesson, None)
        self.assertIn((11, 37, "a", 2), screen.output)
        self.assertIn((12, 2, "x", 3 | curses.A_BOLD), screen.output)
        self.assertTrue(lesson.complete)
        self.assertEqual(lesson.remaining, 0)
        self.assertEqual(lesson.stats.total_hits, 35)
        self.assertEqual(lesson.stats.total_errors, 1)

    @patch("main.curses.curs_set")
    @patch("main.curses.has_colors", return_value=False)
    @patch("main.curses.color_pair", return_value=0)
    @patch("main.draw", return_value=0)
    def test_enter_starts_fresh_lesson_and_function_keys_are_not_input(self, draw_mock, *_):
        waiting_states = []

        def capture_draw(screen, lesson, scroll, *settings):
            if not lesson.history:
                waiting_states.append(lesson.started_at)
            return 0

        draw_mock.side_effect = capture_draw
        screen = Screen(keys=[curses.KEY_F2, "x", "y", "z", "\n", "\x1b"])
        main(screen, 2)
        lessons = [call.args[1] for call in draw_mock.call_args_list]
        self.assertEqual(len(lessons[0].history), 2)
        self.assertTrue(lessons[0].complete)
        self.assertIsNot(lessons[0], lessons[-1])
        self.assertEqual(lessons[-1].stats.total_errors, 0)
        self.assertEqual(lessons[-1].remaining, 2)
        self.assertIsNone(lessons[-1].started_at)
        self.assertTrue(waiting_states)
        self.assertTrue(all(started_at is None for started_at in waiting_states))

    @patch("main.curses.curs_set")
    @patch("main.curses.has_colors", return_value=False)
    @patch("main.draw", return_value=0)
    def test_word_length_option_and_change_on_results_screen(self, draw_mock, *_):
        snapshots = []

        def capture_draw(screen, lesson, scroll, *settings):
            snapshots.append((lesson.sequence_length, len(lesson.target), lesson.complete))
            return 0

        draw_mock.side_effect = capture_draw
        screen = Screen(keys=["x", "y", "z", "w", curses.KEY_F1, "\n", "\x1b"])
        main(screen, lesson_length=4, word_length=3)
        self.assertEqual(snapshots[0], (3, 3, False))
        self.assertEqual(snapshots[-1], (2, 2, False))


if __name__ == "__main__":
    unittest.main()

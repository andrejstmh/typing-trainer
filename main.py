import argparse
import curses
import math
import sys
import time

from config import (CHARSETS, DEFAULT_CHARSET, DEFAULT_LANGUAGE,
                    DEFAULT_LESSON_LENGTH, DEFAULT_SEQUENCE_LENGTH,
                    ERROR_FOREGROUND, TARGET_BACKGROUND, TARGET_FOREGROUND)
from trainer import Generator, Lesson
from characters import normalize_characters
from languages import TEXT, translate


COLORS = {
    name: getattr(curses, "COLOR_" + name.upper())
    for name in ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white")
}
HISTORY_ROW = 11
HISTORY_RESERVED_ROWS = HISTORY_ROW + 3
WORD_COLUMN = 7


def visible_char(char):
    return "␣" if char == " " else char


def input_style(color):
    return curses.color_pair(color) | (curses.A_BOLD if color == 3 else 0)


def initialize_colors(target_foreground, target_background):
    if not curses.has_colors():
        return curses.A_REVERSE
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, COLORS[ERROR_FOREGROUND], curses.COLOR_BLACK)
    curses.init_pair(4, COLORS[target_foreground], COLORS[target_background])
    return curses.color_pair(4)


def put(stdscr, row, col, text, attr=0):
    """Clip output safely, including on small or resized terminals."""
    height, width = stdscr.getmaxyx()
    if 0 <= row < height and 0 <= col < width - 1:
        try:
            stdscr.addstr(row, col, text[:width - col - 1], attr)
        except curses.error:
            pass


def draw(stdscr, lesson, scroll, language=DEFAULT_LANGUAGE, charset=DEFAULT_CHARSET,
         target_style=None):
    def tr(key, **values):
        return translate(language, key, **values)

    stdscr.erase()
    height, width = stdscr.getmaxyx()
    if height < 16 or width < 40:
        put(stdscr, 0, 0, tr("small"))
        stdscr.refresh()
        return scroll or 0

    elapsed = lesson.elapsed(time.perf_counter())
    stats = lesson.stats
    typed = len(lesson.history)
    accuracy = stats.total_hits / typed * 100 if typed else 0
    speed = typed * 60 / elapsed if elapsed else 0
    put(stdscr, 0, 2, tr("complete" if lesson.complete else "title"))
    put(stdscr, 1, 2, tr("progress", remaining=lesson.remaining, length=lesson.length,
                         word_length=lesson.sequence_length))
    put(stdscr, 2, 2, tr("results", hits=stats.total_hits, errors=stats.total_errors, accuracy=accuracy))
    put(stdscr, 3, 2, tr("timing", elapsed=elapsed, speed=speed))
    put(stdscr, 4, 2, tr("average", average=stats.average_last_10))

    if lesson.complete:
        unit = tr("seconds")
        slow_chars = ", ".join(f"{ch}: {value:.2f}{unit}" for ch, value in stats.slowest_chars(3))
        slow_pairs = ", ".join(f"{pair}: {value:.2f}{unit}" for pair, value in stats.slowest_transitions(3))
        put(stdscr, 5, 2, tr("slow_chars") + (slow_chars or "—"))
        put(stdscr, 8, 2, tr("slow_pairs") + (slow_pairs or "—"))
    else:
        put(stdscr, 5, 2, tr("pending" if lesson.pending_characters is not None else "target"))
        if target_style is None:
            target_style = curses.color_pair(4)
        put(stdscr, 6, 0, " " * (width - 1), target_style)
        columns = width - WORD_COLUMN - 1
        offset = min(max(0, len(lesson.target) - columns),
                     max(0, lesson.position - columns + 1))
        target = "".join(map(visible_char, lesson.target[offset:offset + columns]))
        next_col = lesson.position - offset
        if next_col:
            put(stdscr, 6, WORD_COLUMN, target[:next_col], target_style)
        put(stdscr, 6, WORD_COLUMN + next_col, target[next_col], target_style | curses.A_UNDERLINE)
        if target[next_col + 1:]:
            put(stdscr, 6, WORD_COLUMN + 1 + next_col, target[next_col + 1:], target_style)

    if typed and not lesson.history[-1].correct:
        last_press = lesson.history[-1]
        feedback = f"{visible_char(last_press.expected)}→{visible_char(last_press.char)}"
        put(stdscr, 7, WORD_COLUMN, feedback, input_style(3))

    put(stdscr, 9, 2, tr("settings", language=language, charset=charset))
    col = 2
    for color, key in enumerate(("legend_correct", "legend_expected", "legend_error"), 1):
        label = tr(key)
        put(stdscr, 10, col, label, input_style(color))
        col += len(label)
        separator = " | " if color < 3 else " — "
        put(stdscr, 10, col, separator)
        col += len(separator)
    put(stdscr, 10, col, tr("legend_palette"))
    display_chars = []
    for entry in lesson.history:
        if entry.correct:
            display_chars.append((entry.char, 1))
        else:
            display_chars.extend(((entry.expected, 2), (entry.char, 3)))
    columns = width - 4
    rows = height - HISTORY_RESERVED_ROWS
    total_rows = max(1, math.ceil(len(display_chars) / columns))
    max_scroll = max(0, total_rows - rows)
    scroll = max_scroll if scroll is None else min(max(0, scroll), max_scroll)
    for index in range(scroll * columns, min(len(display_chars), (scroll + rows) * columns)):
        char, color = display_chars[index]
        put(stdscr, HISTORY_ROW + index // columns - scroll, 2 + index % columns, char,
            input_style(color))
    put(stdscr, height - 3, 2, tr("scroll", first=scroll + 1,
                                last=min(scroll + rows, total_rows), total=total_rows))
    put(stdscr, height - 2, 2, tr("restart" if lesson.complete else "footer"))
    stdscr.refresh()
    return scroll


def main(stdscr, lesson_length=DEFAULT_LESSON_LENGTH, word_length=DEFAULT_SEQUENCE_LENGTH,
         language=DEFAULT_LANGUAGE, charset=DEFAULT_CHARSET, characters=None,
         target_foreground=TARGET_FOREGROUND, target_background=TARGET_BACKGROUND):
    target_style = initialize_colors(target_foreground, target_background)
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    stdscr.timeout(250)
    sets = dict(CHARSETS)
    if characters is not None:
        sets["custom"] = normalize_characters(characters)
        charset = "custom"
    lesson = Lesson(lesson_length, min(word_length, lesson_length), Generator(sets[charset]))
    scroll = None
    while True:
        current_scroll = draw(stdscr, lesson, scroll, language, charset, target_style)
        try:
            key = stdscr.get_wch()
        except curses.error:
            continue
        if key == "\x1b":
            break
        if key == curses.KEY_RESIZE:
            continue
        if key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
            page = max(1, stdscr.getmaxyx()[0] - HISTORY_RESERVED_ROWS)
            scroll = max(0, current_scroll - page) if key == curses.KEY_PPAGE else current_scroll + page
            continue
        if key == curses.KEY_F1:
            lesson.set_sequence_length(lesson.sequence_length - 1)
            continue
        if key == curses.KEY_F2:
            lesson.set_sequence_length(lesson.sequence_length + 1)
            continue
        if key == curses.KEY_F3:
            languages = list(TEXT)
            language = languages[(languages.index(language) + 1) % len(languages)]
            continue
        if key == curses.KEY_F4:
            names = list(sets)
            charset = names[(names.index(charset) + 1) % len(names)]
            lesson.set_characters(sets[charset])
            continue
        if lesson.complete:
            if key in ("\n", "\r", curses.KEY_ENTER):
                lesson = Lesson(lesson_length, lesson.sequence_length, lesson.generator)
                scroll = None
            continue
        if isinstance(key, str) and key.isprintable():
            lesson.type_char(key, time.perf_counter())
            scroll = None


def positive_int(value, language=DEFAULT_LANGUAGE):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(translate(language, "positive")) from None
    if number < 1:
        raise argparse.ArgumentTypeError(translate(language, "positive"))
    return number


def parse_arguments(argv=None):
    # Select translations before building help, regardless of argument order.
    selector = argparse.ArgumentParser(add_help=False)
    selector.add_argument("--language", choices=tuple(TEXT), default=DEFAULT_LANGUAGE)
    language = selector.parse_known_args(argv)[0].language

    def tr(key):
        return translate(language, key)

    class LocalizedFormatter(argparse.HelpFormatter):
        def add_usage(self, usage, actions, groups, prefix=None):
            super().add_usage(usage, actions, groups, prefix=prefix or tr("usage"))

    class LocalizedParser(argparse.ArgumentParser):
        def error(self, message):
            self.print_usage(sys.stderr)
            self.exit(2, f"{self.prog}: {tr('error')}: {message}\n")

    parser = LocalizedParser(description=tr("description"), add_help=False,
                             formatter_class=LocalizedFormatter)
    parser._optionals.title = tr("options")
    parser.add_argument("-h", "--help", action="help", help=tr("help"))
    parser.add_argument("--language", choices=tuple(TEXT), default=DEFAULT_LANGUAGE,
                        help=tr("language_help"))
    parser.add_argument("--charset", "--layout", choices=tuple(CHARSETS),
                        default=DEFAULT_CHARSET, help=tr("charset_help"))
    parser.add_argument("--chars", help=tr("chars_help"))
    parser.add_argument("--target-fg", choices=tuple(COLORS), default=TARGET_FOREGROUND,
                        help=tr("target_fg_help"))
    parser.add_argument("--target-bg", choices=tuple(COLORS), default=TARGET_BACKGROUND,
                        help=tr("target_bg_help"))
    parser.add_argument("--lesson-length", type=lambda value: positive_int(value, language),
                        default=DEFAULT_LESSON_LENGTH, help=tr("lesson_help"))
    parser.add_argument("--word-length", "--sequence-length", type=lambda value: positive_int(value, language),
                        default=DEFAULT_SEQUENCE_LENGTH,
                        help=tr("word_help"))
    args = parser.parse_args(argv)
    if args.lesson_length < 1 or args.word_length < 1:
        parser.error(tr("positive"))
    if args.chars is not None:
        try:
            args.chars = normalize_characters(args.chars)
        except ValueError:
            parser.error(tr("invalid_chars"))
    return args


if __name__ == "__main__":
    args = parse_arguments()
    curses.wrapper(main, args.lesson_length, args.word_length,
                   args.language, args.charset, args.chars, args.target_fg, args.target_bg)

# Typing Trainer

[Документация на русском](README.ru.md)

A terminal typing trainer with short, configurable lessons. It gives extra practice on slower characters and shows typing speed, accuracy, and errors at the end of each lesson.

## Getting started

Download or clone the project, then open a terminal in its folder. On Windows, use Python 3 and install the [Windows curses package](https://pypi.org/project/windows-curses/) through the requirements file:

```powershell
py -3 -m pip install -r requirements.txt
py -3 main.py
```

You can also run `.\run_typing_trainer.bat`, which forwards command-line options to Python. If `py` is unavailable, use `python` in the commands above. On a machine with a portable Python installation, you can set `TYPING_TRAINER_PYTHON` to the full path of its executable before running the batch file.

## Using the trainer

- **F1/F2** decrease or increase word length.
- **F3** changes the interface language immediately.
- **F4** changes the practice character set. A word already in progress keeps its current set.
- **PgUp/PgDn** scroll through your typing history.
- **Enter** starts another lesson after the results. **Esc** exits.

The target line underlines the next character. When you make a mistake, a hint such as `a→x` below the target shows what was expected and what you actually typed. The hint clears on the next correct keypress. Spaces are shown as `␣` in the hint. An incorrect keypress still counts as one character toward the lesson length. Timing begins with the first character you type.

## Options

The interface and practice character set are both English by default. Choose them independently with `--language` and `--charset` (`--layout` is an alias). Both offer English (`en`), Russian (`ru`), and Latvian (`lv`). F4 changes the exercise characters; use your operating system's keyboard shortcut to switch your actual keyboard layout.

```powershell
py -3 main.py --lesson-length 200 --word-length 5
py -3 main.py --language ru --charset lv
py -3 main.py --chars "asdfjkl;" --word-length 4
py -3 main.py --target-fg black --target-bg cyan
py -3 main.py --help
```

`--chars` overrides the starting character set and adds a `custom` entry to the F4 cycle. Use printable characters that occupy one terminal cell. Duplicate characters are removed.

Set defaults in [`config.py`](config.py), including the interface language, character set, lesson and word lengths, target colors, and error color. Errors use bold yellow by default; try `ERROR_FOREGROUND = "cyan"` if you prefer a blue tone. The labels in the color palette follow the same colors as the history. Changes made with function keys last until you close the program.

To use a larger font in Windows Terminal, set the font size in the profile's **Appearance** settings. A dedicated profile lets you set it to 14 without affecting other tabs.

## Tests

```powershell
py -3 -m unittest
```

DEFAULT_LANGUAGE = "en"
DEFAULT_CHARSET = "en"

# Target row colors: black, red, green, yellow, blue, magenta, cyan, white.
TARGET_FOREGROUND = "black"
TARGET_BACKGROUND = "white"
# Error text on a dark background; try "cyan" for a blue alternative.
ERROR_FOREGROUND = "yellow"

# Independent of interface language. Extend this dictionary to add a practice set.
CHARSETS = {
    "en": "abcdefghijklmnopqrstuvwxyz,.;/",
    "ru": "абвгдеёжзийклмнопрстуфхцчшщъыьэюя.,",
    "lv": "aābcčdeēfgģhiījkķlļmnņoprsštuūvzž,.;/",
}
CHARS = CHARSETS[DEFAULT_CHARSET]

# Default word length; override with --word-length or F1/F2 in the main window.
DEFAULT_SEQUENCE_LENGTH = 1
DEFAULT_LESSON_LENGTH = 200

# Keep adaptive practice varied, even after many lessons.
MIN_CHAR_WEIGHT = 0.75
MAX_CHAR_WEIGHT = 2.0

ROLLING_WINDOW = 10

STATS_FILE = "data/stats.json"

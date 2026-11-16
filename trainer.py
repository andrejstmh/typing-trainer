import random

from config import CHARS, MAX_CHAR_WEIGHT, MIN_CHAR_WEIGHT
from stats import Statistics
from models import TypedCharacter
from characters import normalize_characters


class Lesson:
    """A fixed number of keystrokes with retained per-character history."""

    def __init__(self, length, sequence_length, generator=None):
        if length < 1 or sequence_length < 1:
            raise ValueError("Lesson and sequence lengths must be positive")
        self.length = length
        self.sequence_length = sequence_length
        self.generator = generator if generator is not None else Generator()
        self.stats = Statistics()
        self.history = []
        self.started_at = None
        self.last_time = None
        self.finished_at = None
        self.target = self.generator.next_sequence(min(sequence_length, length))
        self.position = 0
        self.pending_characters = None

    @property
    def remaining(self):
        return self.length - len(self.history)

    @property
    def complete(self):
        return self.remaining == 0

    def start(self, now):
        self.started_at = now
        self.last_time = now

    def set_sequence_length(self, length):
        self.sequence_length = max(1, min(self.length, length))
        # An untouched word can change immediately; keep a partially typed word.
        if not self.complete and self.position == 0:
            self._apply_characters()
            self.target = self.generator.next_sequence(min(self.sequence_length, self.remaining))

    def set_characters(self, characters):
        self.pending_characters = normalize_characters(characters)
        if self.complete or self.position == 0:
            self._apply_characters()
            if not self.complete:
                self.target = self.generator.next_sequence(min(self.sequence_length, self.remaining))

    def _apply_characters(self):
        if self.pending_characters is not None:
            self.generator.set_characters(self.pending_characters)
            self.pending_characters = None
            self.stats.previous_char = None

    def type_char(self, char, now):
        if self.complete:
            return
        if self.started_at is None:
            self.start(now)
        interval = max(0, now - self.last_time)
        expected = self.target[self.position]
        correct = char == expected
        self.history.append(TypedCharacter(char, expected))
        if correct:
            self.stats.add_success(expected, interval)
            self.generator.adapt(expected, interval)
        else:
            self.stats.add_error()
        self.last_time = now
        self.position += 1
        if self.complete:
            self.finished_at = now
        elif self.position == len(self.target):
            self._apply_characters()
            self.target = self.generator.next_sequence(min(self.sequence_length, self.remaining))
            self.position = 0
        if self.complete:
            self._apply_characters()

    def elapsed(self, now):
        if self.started_at is None:
            return 0
        end = self.finished_at if self.finished_at is not None else now
        return max(0, end - self.started_at)


class Generator:

    def __init__(self, characters=CHARS):
        self.weights = {}
        self.set_characters(characters)

    def set_characters(self, characters):
        characters = normalize_characters(characters)
        self.weights = {
            c: self.weights.get(c, 1.0)
            for c in characters
        }

    def adapt(self, char, response_time):

        if response_time > 0.6:
            self.weights[char] = min(MAX_CHAR_WEIGHT, self.weights[char] * 1.15)

        elif response_time < 0.3:
            self.weights[char] = max(MIN_CHAR_WEIGHT, self.weights[char] * 0.97)

    def next_sequence(self, length):

        population = list(self.weights.keys())

        return "".join(
            random.choices(
                population,
                weights=[
                    self.weights[c]
                    for c in population
                ],
                k=length
            )
        )

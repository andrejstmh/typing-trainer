from collections import deque, defaultdict
from statistics import mean


class Statistics:

    def __init__(self, rolling_window=10):

        self.last_times = deque(maxlen=rolling_window)

        self.total_hits = 0
        self.total_errors = 0

        self.char_stats = defaultdict(list)
        self.transition_stats = defaultdict(list)

        self.previous_char = None

    def add_success(self, char, interval):

        self.total_hits += 1

        self.last_times.append(interval)

        self.char_stats[char].append(interval)

        if self.previous_char:
            key = f"{self.previous_char}->{char}"
            self.transition_stats[key].append(interval)

        self.previous_char = char

    def add_error(self):
        self.total_errors += 1
        self.previous_char = None

    @property
    def average_last_10(self):

        if not self.last_times:
            return 0

        return mean(self.last_times)

    @property
    def cpm(self):

        avg = self.average_last_10

        if avg == 0:
            return 0

        return 60 / avg

    def slowest_chars(self, count=5):

        result = []

        for char, values in self.char_stats.items():
            result.append(
                (
                    char,
                    mean(values)
                )
            )

        result.sort(key=lambda x: x[1], reverse=True)

        return result[:count]

    def slowest_transitions(self, count=5):

        result = []

        for tr, values in self.transition_stats.items():
            result.append(
                (
                    tr,
                    mean(values)
                )
            )

        result.sort(key=lambda x: x[1], reverse=True)

        return result[:count]

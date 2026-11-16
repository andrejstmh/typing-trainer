from dataclasses import dataclass


@dataclass(frozen=True)
class TypedCharacter:
    char: str
    expected: str

    @property
    def correct(self):
        return self.char == self.expected


@dataclass
class Attempt:
    char: str
    response_time: float
    success: bool

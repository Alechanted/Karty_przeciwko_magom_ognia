from enum import Enum

class Phase(str, Enum):
    LOBBY = "LOBBY"
    SELECTING = "SELECTING"
    JUDGING = "JUDGING"
    SUMMARY = "SUMMARY"
    GAME_OVER = "GAME_OVER"
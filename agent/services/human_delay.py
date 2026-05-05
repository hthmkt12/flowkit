"""FBKit — Human-like delay and behavior simulation.

Prevents detection by mimicking natural human interaction patterns:
random delays, typing speed variation, and session management.
"""
import asyncio
import logging
import random
import time

from agent.config import (
    ACTION_DELAY_MIN, ACTION_DELAY_MAX,
    TYPING_DELAY_MIN, TYPING_DELAY_MAX,
    SESSION_ACTIVE_MIN, SESSION_ACTIVE_MAX,
    SESSION_BREAK_MIN, SESSION_BREAK_MAX,
)

logger = logging.getLogger(__name__)


async def action_delay(min_s: float = None, max_s: float = None):
    """Random delay between actions (simulates human thinking time)."""
    lo = min_s or ACTION_DELAY_MIN
    hi = max_s or ACTION_DELAY_MAX
    delay = random.uniform(lo, hi)
    logger.debug("Action delay: %.1fs", delay)
    await asyncio.sleep(delay)


async def short_delay():
    """Very short delay (0.3-1.2s) — between sub-actions like click → type."""
    delay = random.uniform(0.3, 1.2)
    await asyncio.sleep(delay)


async def medium_delay():
    """Medium delay (1.5-4s) — between related actions like typing → submit."""
    delay = random.uniform(1.5, 4.0)
    await asyncio.sleep(delay)


async def long_delay():
    """Long delay (5-15s) — between unrelated actions or after completing a task."""
    delay = random.uniform(5.0, 15.0)
    logger.debug("Long delay: %.1fs", delay)
    await asyncio.sleep(delay)


def get_typing_delays(text: str) -> list[int]:
    """Generate per-character typing delays (ms) for realistic typing simulation.

    Returns a list of delays in milliseconds, one per character.
    Patterns:
    - Space/punctuation: slightly longer pause
    - After newline: longer pause (thinking)
    - Normal chars: random within range
    - Occasional burst typing (faster for 3-5 chars)
    """
    delays = []
    burst_counter = 0
    burst_len = 0

    for i, char in enumerate(text):
        if burst_counter > 0:
            # In a burst — type faster
            d = random.randint(TYPING_DELAY_MIN // 2, TYPING_DELAY_MIN)
            burst_counter -= 1
        elif char in (' ', '.', ',', '!', '?', ';', ':'):
            # Punctuation — slight pause
            d = random.randint(TYPING_DELAY_MAX, TYPING_DELAY_MAX + 80)
        elif char == '\n':
            # Newline — thinking pause
            d = random.randint(300, 800)
        else:
            d = random.randint(TYPING_DELAY_MIN, TYPING_DELAY_MAX)
            # Random chance of burst typing
            if random.random() < 0.1 and i < len(text) - 5:
                burst_counter = random.randint(3, 6)

        delays.append(d)

    return delays


def total_typing_time(text: str) -> float:
    """Estimate total typing time in seconds."""
    delays = get_typing_delays(text)
    return sum(delays) / 1000.0


class SessionManager:
    """Manages active/break sessions to mimic natural usage patterns.

    A real user doesn't use Facebook continuously. They browse for 1-3 hours,
    then take a break. This manager enforces that pattern.
    """

    def __init__(self):
        self._session_start: float | None = None
        self._session_duration: float = 0  # seconds
        self._break_until: float | None = None
        self._actions_this_session: int = 0

    def start_session(self):
        """Start a new active session."""
        self._session_start = time.time()
        self._session_duration = random.uniform(
            SESSION_ACTIVE_MIN * 60,
            SESSION_ACTIVE_MAX * 60
        )
        self._actions_this_session = 0
        logger.info("Session started (%.0f min limit)", self._session_duration / 60)

    def should_take_break(self) -> bool:
        """Check if it's time for a break."""
        if self._break_until:
            if time.time() < self._break_until:
                return True
            else:
                # Break is over
                self._break_until = None
                self.start_session()
                return False

        if self._session_start is None:
            self.start_session()
            return False

        elapsed = time.time() - self._session_start
        return elapsed >= self._session_duration

    def take_break(self) -> float:
        """Start a break. Returns break duration in seconds."""
        duration = random.uniform(
            SESSION_BREAK_MIN * 60,
            SESSION_BREAK_MAX * 60
        )
        self._break_until = time.time() + duration
        self._session_start = None
        logger.info("Taking a break for %.0f min", duration / 60)
        return duration

    def record_action(self):
        """Record that an action was performed."""
        self._actions_this_session += 1

    @property
    def session_info(self) -> dict:
        if self._break_until:
            remaining = max(0, self._break_until - time.time())
            return {"state": "break", "remaining_s": int(remaining)}
        if self._session_start:
            elapsed = time.time() - self._session_start
            remaining = max(0, self._session_duration - elapsed)
            return {
                "state": "active",
                "elapsed_s": int(elapsed),
                "remaining_s": int(remaining),
                "actions": self._actions_this_session,
            }
        return {"state": "idle"}


# Singleton
_session = SessionManager()


def get_session_manager() -> SessionManager:
    return _session

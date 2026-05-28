"""PTY-backed terminal with pyte ANSI emulation.

Spawns bash on a pseudo-terminal so vim, htop, paginated git log, ssh, and
other curses-style apps all render correctly. Bytes from the PTY master are
fed into pyte.Screen; the screen buffer is rendered to a custom paint widget
with per-character colors and a block cursor.

Keys are translated to terminal escape sequences and written to the PTY master.

Linux-only: relies on pty.fork() and TIOCSWINSZ.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import pty
import shutil
import signal
import struct
import termios
from pathlib import Path

import pyte
from PySide6.QtCore import QObject, QSocketNotifier, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QPainter,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_ANSI_COLORS = {
    "black": "#000000",
    "red": "#cc6666",
    "green": "#b5bd68",
    "brown": "#f0c674",
    "blue": "#81a2be",
    "magenta": "#b294bb",
    "cyan": "#8abeb7",
    "white": "#c5c8c6",
    "default": "#d8d8d8",
}
_DEFAULT_FG = "#d8d8d8"
_DEFAULT_BG = "#111111"


def _resolve_color(name: str, default: str) -> str:
    if name.startswith("#"):
        return name
    if len(name) == 6 and all(c in "0123456789abcdef" for c in name.lower()):
        return "#" + name
    return _ANSI_COLORS.get(name, default)


class PtyWorker(QObject):
    output_chunk = Signal(bytes)
    process_exited = Signal(int)

    def __init__(self, cols: int, rows: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cols = cols
        self._rows = rows
        self._pid: int = 0
        self._fd: int = -1
        self._notifier: QSocketNotifier | None = None

    @property
    def fd(self) -> int:
        return self._fd

    def start(self) -> None:
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["PS1"] = r"\u@\h \w$ "
        env.pop("PROMPT_COMMAND", None)

        shell = shutil.which("bash") or "/bin/bash"
        cwd = str(Path.home())

        pid, fd = pty.fork()
        if pid == 0:
            with contextlib.suppress(OSError):
                os.chdir(cwd)
            for k, v in env.items():
                os.environ[k] = v
            os.execvp(shell, [shell, "--login"])
            os._exit(127)

        self._pid = pid
        self._fd = fd
        self._set_winsize(self._cols, self._rows)
        self._notifier = QSocketNotifier(fd, QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._on_readable)

    def stop(self) -> None:
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier = None
        if self._pid:
            with contextlib.suppress(ProcessLookupError):
                os.kill(self._pid, signal.SIGHUP)
            with contextlib.suppress(ChildProcessError):
                os.waitpid(self._pid, os.WNOHANG)
            self._pid = 0
        if self._fd >= 0:
            with contextlib.suppress(OSError):
                os.close(self._fd)
            self._fd = -1

    def write(self, data: bytes) -> None:
        if self._fd >= 0:
            with contextlib.suppress(OSError):
                os.write(self._fd, data)

    def resize(self, cols: int, rows: int) -> None:
        self._cols, self._rows = cols, rows
        if self._fd >= 0:
            self._set_winsize(cols, rows)
            if self._pid:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(self._pid, signal.SIGWINCH)

    def _set_winsize(self, cols: int, rows: int) -> None:
        with contextlib.suppress(OSError):
            fcntl.ioctl(self._fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def _on_readable(self, _fd: int) -> None:
        try:
            data = os.read(self._fd, 32768)
        except OSError:
            self.process_exited.emit(-1)
            return
        if not data:
            self.process_exited.emit(0)
            return
        self.output_chunk.emit(data)


class TerminalView(QWidget):
    key_pressed = Signal(bytes)
    size_changed = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.setFont(font)
        fm = QFontMetricsF(font)
        self._cell_w = fm.horizontalAdvance("M")
        self._cell_h = fm.height()
        self._ascent = fm.ascent()

        self._screen: pyte.Screen | None = None
        self._cols = 100
        self._rows = 30

        self.setMinimumSize(int(self._cell_w * 40), int(self._cell_h * 10))

    def set_screen(self, screen: pyte.Screen) -> None:
        self._screen = screen
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        cols = max(20, int(event.size().width() / self._cell_w))
        rows = max(5, int(event.size().height() / self._cell_h))
        if (cols, rows) != (self._cols, self._rows):
            self._cols, self._rows = cols, rows
            self.size_changed.emit(cols, rows)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(_DEFAULT_BG))
        if self._screen is None:
            painter.end()
            return
        painter.setFont(self.font())

        buf = self._screen.buffer
        cursor_x = self._screen.cursor.x
        cursor_y = self._screen.cursor.y
        cursor_hidden = self._screen.cursor.hidden

        for y in range(min(self._rows, self._screen.lines)):
            row = buf[y]
            for x in range(min(self._cols, self._screen.columns)):
                ch = row[x]
                if not ch.data:
                    continue
                fg = _resolve_color(ch.fg, _DEFAULT_FG)
                bg = _resolve_color(ch.bg, _DEFAULT_BG)
                if ch.reverse:
                    fg, bg = bg, fg
                is_cursor = (not cursor_hidden) and x == cursor_x and y == cursor_y
                if is_cursor:
                    fg, bg = _DEFAULT_BG, _DEFAULT_FG
                px = x * self._cell_w
                py = y * self._cell_h
                if bg != _DEFAULT_BG or is_cursor:
                    painter.fillRect(
                        int(px), int(py),
                        int(self._cell_w) + 1, int(self._cell_h) + 1,
                        QColor(bg),
                    )
                painter.setPen(QColor(fg))
                painter.drawText(int(px), int(py + self._ascent), ch.data)

        if not cursor_hidden and cursor_x < self._screen.columns and cursor_y < self._screen.lines:
            row = buf[cursor_y]
            if not row[cursor_x].data:
                px = cursor_x * self._cell_w
                py = cursor_y * self._cell_h
                painter.fillRect(
                    int(px), int(py),
                    int(self._cell_w) + 1, int(self._cell_h) + 1,
                    QColor(_DEFAULT_FG),
                )
        painter.end()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        data = self._key_to_bytes(event)
        if data:
            self.key_pressed.emit(data)
            event.accept()
            return
        super().keyPressEvent(event)

    def _key_to_bytes(self, e: QKeyEvent) -> bytes:
        k = e.key()
        mods = e.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)

        special = {
            Qt.Key.Key_Up: b"\x1b[A",
            Qt.Key.Key_Down: b"\x1b[B",
            Qt.Key.Key_Right: b"\x1b[C",
            Qt.Key.Key_Left: b"\x1b[D",
            Qt.Key.Key_Home: b"\x1b[H",
            Qt.Key.Key_End: b"\x1b[F",
            Qt.Key.Key_PageUp: b"\x1b[5~",
            Qt.Key.Key_PageDown: b"\x1b[6~",
            Qt.Key.Key_Insert: b"\x1b[2~",
            Qt.Key.Key_Delete: b"\x1b[3~",
            Qt.Key.Key_Backspace: b"\x7f",
            Qt.Key.Key_Tab: b"\t",
            Qt.Key.Key_Backtab: b"\x1b[Z",
            Qt.Key.Key_Return: b"\r",
            Qt.Key.Key_Enter: b"\r",
            Qt.Key.Key_Escape: b"\x1b",
            Qt.Key.Key_F1: b"\x1bOP",
            Qt.Key.Key_F2: b"\x1bOQ",
            Qt.Key.Key_F3: b"\x1bOR",
            Qt.Key.Key_F4: b"\x1bOS",
            Qt.Key.Key_F5: b"\x1b[15~",
            Qt.Key.Key_F6: b"\x1b[17~",
            Qt.Key.Key_F7: b"\x1b[18~",
            Qt.Key.Key_F8: b"\x1b[19~",
            Qt.Key.Key_F9: b"\x1b[20~",
            Qt.Key.Key_F10: b"\x1b[21~",
            Qt.Key.Key_F11: b"\x1b[23~",
            Qt.Key.Key_F12: b"\x1b[24~",
        }
        if k in special:
            return special[k]

        if ctrl and Qt.Key.Key_A <= k <= Qt.Key.Key_Z:
            return bytes([k - Qt.Key.Key_A.value + 1])
        if ctrl and k == Qt.Key.Key_BracketLeft:
            return b"\x1b"
        if ctrl and k == Qt.Key.Key_Space:
            return b"\x00"

        text = e.text()
        if not text:
            return b""
        encoded = text.encode("utf-8")
        if alt:
            return b"\x1b" + encoded
        return encoded


class Terminal(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cols = 100
        self._rows = 30
        self._screen = pyte.Screen(self._cols, self._rows)
        self._screen.set_mode(pyte.modes.LNM)
        self._stream = pyte.ByteStream(self._screen)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(6, 2, 6, 2)
        self._status = QLabel("bash (PTY)")
        self._status.setStyleSheet("color: #888;")
        header.addWidget(self._status, 1)
        self._restart_btn = QPushButton("Restart")
        self._restart_btn.setFlat(True)
        self._restart_btn.clicked.connect(self._restart)
        header.addWidget(self._restart_btn)
        outer.addLayout(header)

        self._view = TerminalView(self)
        self._view.set_screen(self._screen)
        self._view.key_pressed.connect(self._on_key)
        self._view.size_changed.connect(self._on_resize)
        outer.addWidget(self._view, 1)

        self._worker: PtyWorker | None = None
        self._start()

    def _start(self) -> None:
        self._worker = PtyWorker(self._cols, self._rows, self)
        self._worker.output_chunk.connect(self._on_chunk)
        self._worker.process_exited.connect(self._on_exit)
        self._worker.start()
        self._status.setText(f"bash (PTY) — {self._cols}x{self._rows}")

    def _restart(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
        self._screen.reset()
        self._screen.resize(self._rows, self._cols)
        self._view.update()
        self._start()

    def _on_chunk(self, data: bytes) -> None:
        self._stream.feed(data)
        self._view.update()

    def _on_exit(self, code: int) -> None:
        self._status.setText(f"bash exited (rc={code}) — click Restart")
        if self._worker is not None:
            self._worker.stop()
            self._worker = None

    def _on_key(self, data: bytes) -> None:
        if self._worker is not None:
            self._worker.write(data)

    def _on_resize(self, cols: int, rows: int) -> None:
        self._cols, self._rows = cols, rows
        self._screen.resize(rows, cols)
        if self._worker is not None:
            self._worker.resize(cols, rows)
        self._status.setText(f"bash (PTY) — {cols}x{rows}")

    def focus_input(self) -> None:
        self._view.setFocus(Qt.FocusReason.OtherFocusReason)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
        super().closeEvent(event)

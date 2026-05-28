"""Embedded bash terminal panel.

QProcess-backed persistent bash (non-TTY). Good for normal shell work — ls, git,
grep, cat, pipes, redirections. Fullscreen TUI apps (vim, htop) won't render
properly because there's no PTY emulation; for those, use a real terminal.

ANSI escape codes are stripped from output so the QPlainTextEdit stays clean.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    # PySide6 ships QtCore.QProcess; importing it lazily for clarity
    from PySide6.QtCore import QProcess
except ImportError:  # pragma: no cover
    QProcess = None  # type: ignore[assignment]


# ANSI / OSC escape sequences (CSI, OSC, CR-only carriage returns, BEL)
_ANSI_RE = re.compile(
    r"\x1B(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1B]*(?:\x07|\x1B\\))"
)
_BEL_RE = re.compile(r"\x07")


def _strip_ansi(text: str) -> str:
    return _BEL_RE.sub("", _ANSI_RE.sub("", text))


class CommandLine(QLineEdit):
    """LineEdit with up/down history and Ctrl+C clears the input."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history: list[str] = []
        self._cursor: int = 0
        self.setPlaceholderText("type a command and hit Enter")

    def push(self, cmd: str) -> None:
        if cmd and (not self._history or self._history[-1] != cmd):
            self._history.append(cmd)
        self._cursor = len(self._history)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Up:
            if self._history and self._cursor > 0:
                self._cursor -= 1
                self.setText(self._history[self._cursor])
            return
        if event.key() == Qt.Key.Key_Down:
            if self._cursor < len(self._history) - 1:
                self._cursor += 1
                self.setText(self._history[self._cursor])
            else:
                self._cursor = len(self._history)
                self.clear()
            return
        if event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.clear()
            return
        super().keyPressEvent(event)


class Terminal(QWidget):
    """Persistent-bash terminal panel.

    Commands go to stdin; merged stdout/stderr stream back. State (cwd, env,
    shell variables) persists across commands.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Output area
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self._out.setFont(font)
        self._out.setStyleSheet(
            "QPlainTextEdit { background-color: #111; color: #d8d8d8; }"
        )
        self._out.setMaximumBlockCount(20000)  # rolling scrollback
        layout.addWidget(self._out, 1)

        # Toolbar row
        row = QHBoxLayout()
        self._prompt = QLabel("$")
        self._prompt.setStyleSheet("color: #6a6;")
        self._prompt.setFont(font)
        row.addWidget(self._prompt)

        self._input = CommandLine()
        self._input.setFont(font)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input, 1)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._out.clear)
        row.addWidget(self._clear_btn)

        self._restart_btn = QPushButton("Restart shell")
        self._restart_btn.clicked.connect(self._restart)
        row.addWidget(self._restart_btn)
        layout.addLayout(row)

        self._start()

    # ---------- lifecycle ----------

    def _start(self) -> None:
        if QProcess is None:
            self._append("[QProcess unavailable]\n", color="#e66")
            return
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        home = str(Path.home())
        proc.setWorkingDirectory(home)
        env = proc.processEnvironment()
        env.insert("PS1", "")
        env.insert("TERM", "dumb")
        proc.setProcessEnvironment(env)
        proc.readyReadStandardOutput.connect(self._read)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        # bash without rc files keeps the prompt out of the way
        proc.start("/bin/bash", ["--norc", "--noprofile"])
        self._proc = proc
        self._append(f"bash started in {home}\n", color="#6a6")

    def _restart(self) -> None:
        if self._proc is not None:
            self._proc.kill()
            self._proc.waitForFinished(2000)
            self._proc = None
        self._out.clear()
        self._start()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._proc is not None:
            self._proc.kill()
            self._proc.waitForFinished(2000)
            self._proc = None
        super().closeEvent(event)

    # ---------- I/O ----------

    def _send(self) -> None:
        cmd = self._input.text()
        if not cmd:
            return
        self._input.push(cmd)
        self._input.clear()
        self._append(f"$ {cmd}\n", color="#9cf")
        if self._proc is None or self._proc.state() != QProcess.ProcessState.Running:
            self._append("[shell not running — click 'Restart shell']\n", color="#e66")
            return
        self._proc.write((cmd + "\n").encode("utf-8"))

    def _read(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput().data())
        if not data:
            return
        text = data.decode("utf-8", errors="replace")
        self._append(_strip_ansi(text))

    def _on_finished(self, code: int, _status: object) -> None:
        self._append(f"[shell exited with code {code}]\n", color="#e66")
        self._proc = None

    def _on_error(self, err: object) -> None:
        self._append(f"[shell error: {err}]\n", color="#e66")

    def _append(self, text: str, *, color: str | None = None) -> None:
        cursor = self._out.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if color:
            cursor.insertHtml(
                f'<span style="color:{color};white-space:pre">'
                f'{_html_escape(text)}'
                f'</span>'
            )
        else:
            cursor.insertText(text)
        self._out.setTextCursor(cursor)
        self._out.ensureCursorVisible()

    def focus_input(self) -> None:
        self._input.setFocus(Qt.FocusReason.OtherFocusReason)


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace("\n", "<br>")
    )

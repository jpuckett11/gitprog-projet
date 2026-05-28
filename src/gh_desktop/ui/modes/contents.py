"""Contents mode — browse repository files.

Layout:
  Toolbar: scope (owner/repo), branch combo, refresh
  Left:    Lazy-loaded tree (folders expand on click via /contents)
  Right:   File viewer — markdown for .md, plain text for code, hex for binary,
           inline image for png/jpg/gif/svg.

Files larger than MAX_FILE_BYTES are not loaded (link-out only).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gh_desktop.api.services import ContentsService
from gh_desktop.api.services.contents import ContentEntry, FileBlob
from gh_desktop.ui.widgets import MarkdownView, StatusBanner, run_async
from gh_desktop.workspace import Workspace

MAX_FILE_BYTES = 1_500_000  # ~1.5 MB; bigger files render too slowly in QTextEdit

_TEXT_EXTS = {
    "txt", "md", "rst", "py", "js", "ts", "tsx", "jsx", "go", "rs", "c", "h", "cpp",
    "hpp", "cs", "java", "kt", "rb", "php", "sh", "bash", "zsh", "fish", "lua",
    "sql", "yaml", "yml", "toml", "ini", "cfg", "conf", "json", "xml", "html", "htm",
    "css", "scss", "less", "vue", "svelte", "swift", "m", "mm", "scala", "clj",
    "ex", "exs", "erl", "hs", "ml", "fs", "fsx", "r", "jl", "dart", "tf",
    "gitignore", "gitattributes", "dockerfile", "makefile", "cmake",
}
_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg"}


def _ext(name: str) -> str:
    if "." in name:
        return name.rsplit(".", 1)[-1].lower()
    return name.lower()


class ContentsMode(QWidget):
    def __init__(self, workspace: Workspace, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._svc = ContentsService(workspace.rest)
        self._scope: tuple[str, str] | None = None  # (owner, repo)
        self._branch: str = ""
        self._workers: list[Any] = []  # keep refs

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.addWidget(QLabel("Repo:"))
        self._repo_input = QLineEdit()
        self._repo_input.setPlaceholderText("owner/repo")
        self._repo_input.returnPressed.connect(self._on_scope_changed)
        toolbar.addWidget(self._repo_input, 2)

        toolbar.addWidget(QLabel("Branch:"))
        self._branch_combo = QComboBox()
        self._branch_combo.setMinimumWidth(160)
        self._branch_combo.currentTextChanged.connect(self._on_branch_changed)
        toolbar.addWidget(self._branch_combo, 1)

        self._load_btn = QPushButton("Load")
        self._load_btn.clicked.connect(self._on_scope_changed)
        toolbar.addWidget(self._load_btn)
        outer.addLayout(toolbar)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        # tree + viewer
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Path", "Size"])
        self._tree.itemExpanded.connect(self._on_expand)
        self._tree.itemActivated.connect(self._on_activate)
        splitter.addWidget(self._tree)

        # right side: stacked viewer (text / markdown / image / binary)
        self._stack = QStackedWidget()
        self._md_view = MarkdownView()
        self._text_view = QPlainTextEdit()
        self._text_view.setReadOnly(True)
        self._text_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._image_label = QLabel("")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setScaledContents(False)
        self._info = QLabel("Select a file in the tree.")
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info.setStyleSheet("color: #888;")

        self._stack.addWidget(self._info)         # 0 — empty/info
        self._stack.addWidget(self._md_view)      # 1 — markdown
        self._stack.addWidget(self._text_view)    # 2 — text/code
        self._stack.addWidget(self._image_label)  # 3 — image
        splitter.addWidget(self._stack)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([360, 800])
        outer.addWidget(splitter, 1)

    # ---------- scope ----------

    def set_scope(self, owner_repo: str) -> None:
        if "/" not in owner_repo:
            return
        self._repo_input.setText(owner_repo)
        self._on_scope_changed()

    def _on_scope_changed(self) -> None:
        text = self._repo_input.text().strip()
        if "/" not in text:
            self._banner.show_error("Enter a scope as owner/repo.")
            return
        owner, repo = text.split("/", 1)
        self._scope = (owner, repo)
        self._tree.clear()
        self._load_branches_and_root()

    def _on_branch_changed(self, branch: str) -> None:
        if self._branch == branch or not branch or self._scope is None:
            return
        self._branch = branch
        self._tree.clear()
        self._load_root()

    # ---------- loaders ----------

    def _load_branches_and_root(self) -> None:
        if self._scope is None:
            return
        owner, repo = self._scope
        svc = self._svc
        self._banner.show_busy("Loading branches…")

        async def fetch() -> list[str]:
            return await svc.list_branches(owner, repo)

        def on_branches(branches: list[str]) -> None:
            preferred = ("main", "master", "develop", "trunk")
            self._branch_combo.blockSignals(True)
            self._branch_combo.clear()
            ordered = sorted(branches, key=lambda b: (b not in preferred, b))
            self._branch_combo.addItems(ordered)
            self._branch_combo.blockSignals(False)
            if ordered:
                self._branch = ordered[0]
                self._branch_combo.setCurrentText(self._branch)
                self._load_root()
            else:
                # No branches means the repo has no commits yet.
                self._branch = ""
                self._tree.clear()
                self._banner.show_info("Repository is empty — no branches yet.")
                self._info.setText("This repository has no commits yet.")
                self._stack.setCurrentWidget(self._info)

        self._workers.append(
            run_async(self, fetch, on_success=on_branches, on_failure=self._on_error)
        )

    def _load_root(self) -> None:
        if self._scope is None:
            return
        owner, repo = self._scope
        branch = self._branch or None
        svc = self._svc
        self._banner.show_busy("Loading repository tree…")

        async def fetch() -> list[ContentEntry]:
            return await svc.list_dir(owner, repo, "", branch)

        def on_root(entries: list[ContentEntry]) -> None:
            self._tree.clear()
            if not entries:
                self._banner.show_info("Repository is empty.")
                self._info.setText("This repository has no files yet.")
                self._stack.setCurrentWidget(self._info)
                return
            for e in _sorted(entries):
                self._tree.addTopLevelItem(_make_item(e))
            self._banner.setVisible(False)

        self._workers.append(
            run_async(self, fetch, on_success=on_root, on_failure=self._on_error)
        )

    def _on_expand(self, item: QTreeWidgetItem) -> None:
        # Lazy-load directory children on first expand.
        data: ContentEntry | None = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None or data.type != "dir":
            return
        if item.childCount() and item.child(0).text(0) != "(loading…)":
            return  # already loaded
        # replace any placeholder
        while item.childCount():
            item.removeChild(item.child(0))
        placeholder = QTreeWidgetItem(item, ["(loading…)", ""])
        placeholder.setFlags(Qt.ItemFlag.NoItemFlags)

        if self._scope is None:
            return
        owner, repo = self._scope
        path = data.path
        branch = self._branch or None
        svc = self._svc

        async def fetch() -> list[ContentEntry]:
            return await svc.list_dir(owner, repo, path, branch)

        def on_done(entries: list[ContentEntry]) -> None:
            while item.childCount():
                item.removeChild(item.child(0))
            for e in _sorted(entries):
                item.addChild(_make_item(e))

        self._workers.append(
            run_async(self, fetch, on_success=on_done, on_failure=self._on_error)
        )

    def _on_activate(self, item: QTreeWidgetItem, _col: int) -> None:
        data: ContentEntry | None = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return
        if data.type == "dir":
            item.setExpanded(not item.isExpanded())
            return
        if data.type != "file":
            return
        if data.size > MAX_FILE_BYTES:
            self._show_too_big(data)
            return
        self._load_file(data)

    def _load_file(self, entry: ContentEntry) -> None:
        if self._scope is None:
            return
        owner, repo = self._scope
        path = entry.path
        branch = self._branch or None
        svc = self._svc

        self._banner.show_busy(f"Loading {path}…")

        async def fetch() -> FileBlob:
            return await svc.get_file(owner, repo, path, branch)

        def on_done(blob: FileBlob) -> None:
            self._banner.setVisible(False)
            self._render_blob(entry, blob)

        self._workers.append(
            run_async(self, fetch, on_success=on_done, on_failure=self._on_error)
        )

    # ---------- rendering ----------

    def _render_blob(self, entry: ContentEntry, blob: FileBlob) -> None:
        ext = _ext(entry.name)
        raw = blob.decode_bytes() or b""

        if ext in _IMAGE_EXTS and ext != "svg":
            pix = QPixmap()
            if pix.loadFromData(raw):
                self._image_label.setPixmap(pix)
                self._stack.setCurrentWidget(self._image_label)
                return

        if ext == "md":
            try:
                self._md_view.set_markdown(raw.decode("utf-8", errors="replace"))
                self._stack.setCurrentWidget(self._md_view)
                return
            except Exception:
                pass

        if ext in _TEXT_EXTS or _looks_textual(raw):
            self._text_view.setPlainText(raw.decode("utf-8", errors="replace"))
            self._stack.setCurrentWidget(self._text_view)
            return

        # binary fallback — show a hex preview of the first 1024 bytes
        preview = _hex_preview(raw[:1024])
        self._text_view.setPlainText(
            f"Binary file ({len(raw)} bytes). First 1 KB:\n\n{preview}"
        )
        self._stack.setCurrentWidget(self._text_view)

    def _show_too_big(self, entry: ContentEntry) -> None:
        self._info.setText(
            f"{entry.path}\n\nFile is {entry.size:,} bytes — too large to preview inline.\n"
            f"Open on GitHub: {entry.html_url or '—'}"
        )
        self._stack.setCurrentWidget(self._info)
        if entry.html_url:
            QDesktopServices.openUrl  # noqa: B018  (UI hint — open via menu/click)

    def _on_error(self, exc: Exception) -> None:
        self._banner.show_error(f"Contents: {exc}")


# ---------- helpers ----------

def _make_item(entry: ContentEntry) -> QTreeWidgetItem:
    icon = "📁 " if entry.type == "dir" else ""
    label = f"{icon}{entry.name}"
    size = "" if entry.type == "dir" else f"{entry.size:,}"
    item = QTreeWidgetItem([label, size])
    item.setData(0, Qt.ItemDataRole.UserRole, entry)
    if entry.type == "dir":
        # placeholder child so the chevron renders before we lazy-load
        placeholder = QTreeWidgetItem(item, ["(loading…)", ""])
        placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
    return item


def _sorted(entries: list[ContentEntry]) -> list[ContentEntry]:
    # Dirs first (alpha), then files (alpha) — common file-explorer convention
    return sorted(entries, key=lambda e: (e.type != "dir", e.name.lower()))


def _looks_textual(b: bytes) -> bool:
    if not b:
        return True
    if b[:3] == b"\xef\xbb\xbf":  # UTF-8 BOM
        return True
    # Heuristic: >95% printable / common whitespace
    sample = b[:4096]
    if b"\x00" in sample:
        return False
    printable = sum(1 for c in sample if 9 <= c < 127 or c in (10, 13))
    return printable / max(1, len(sample)) > 0.95


def _hex_preview(b: bytes) -> str:
    lines = []
    for i in range(0, len(b), 16):
        chunk = b[i : i + 16]
        hex_part = " ".join(f"{c:02x}" for c in chunk).ljust(48)
        ascii_part = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        lines.append(f"{i:08x}  {hex_part}  |{ascii_part}|")
    return "\n".join(lines)

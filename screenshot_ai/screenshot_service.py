import hashlib
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Set, Union

from PIL import Image, ImageGrab
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .gemini_service import SUPPORTED_EXTS


class ScreenshotError(Exception):
    pass


class ScreenshotService:
    def __init__(self):
        self.processed_hashes: Set[str] = set()
        self.observer: Optional[Observer] = None
        self._callback: Optional[Callable[[str], None]] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ files --
    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of a file so identical images are not re-sent."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as handle:
                for block in iter(lambda: handle.read(65536), b""):
                    sha256_hash.update(block)
            return sha256_hash.hexdigest()
        except OSError as exc:
            raise ScreenshotError(f"Failed to read file: {exc}") from exc

    def validate_screenshot(self, file_path: str) -> Path:
        """Validate screenshot extension and that Pillow can open it."""
        path = Path(file_path)
        if not path.exists():
            raise ScreenshotError(f"File not found: {path}")
        if not path.is_file():
            raise ScreenshotError(f"Not a file: {path}")
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTS:
            raise ScreenshotError(
                f"Unsupported format '{ext}'. Supported: PNG, JPG, JPEG"
            )
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:  # noqa: BLE001 - Pillow raises many types
            raise ScreenshotError(f"Unreadable or corrupted image: {exc}") from exc
        return path

    def is_already_processed(self, file_path: str) -> bool:
        try:
            file_hash = self.compute_file_hash(file_path)
        except ScreenshotError:
            return False
        with self._lock:
            return file_hash in self.processed_hashes

    def mark_processed(self, file_path: str) -> None:
        try:
            file_hash = self.compute_file_hash(file_path)
        except ScreenshotError:
            return
        with self._lock:
            self.processed_hashes.add(file_hash)

    # ----------------------------------------------------------------- picker --
    def select_screenshot_file(self, parent=None) -> Optional[str]:
        """Open the file dialog and return a validated path (or None)."""
        try:
            from PySide6.QtWidgets import QFileDialog
        except ImportError as exc:  # pragma: no cover
            raise ScreenshotError(f"PySide6 is not available: {exc}") from exc

        file_filter = (
            "Images (*.png *.jpg *.jpeg);;"
            "PNG (*.png);;"
            "JPEG (*.jpg *.jpeg);;"
            "All Files (*.*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(
            parent, "Select Screenshot", "", file_filter
        )
        if not file_path:
            return None
        self.validate_screenshot(file_path)
        return file_path

    # --------------------------------------------------------------- clipboard --
    def grab_clipboard_image(self) -> Optional[str]:
        """Return a usable image path from the clipboard, or ``None``.

        Handles the two shapes Windows exposes to Pillow:
        * a bitmap (what ``Win+Shift+S`` copies), saved as a temporary PNG;
        * a list of copied files (Explorer "Copy"), using the first image.
        """
        try:
            data = ImageGrab.grabclipboard()
        except Exception as exc:  # noqa: BLE001 - clipboard can be locked
            raise ScreenshotError(
                f"Could not read the clipboard: {exc}. Try copying the snip again."
            ) from exc

        if data is None:
            return None

        if isinstance(data, list):
            for item in data:
                candidate = Path(str(item))
                if candidate.suffix.lower() in SUPPORTED_EXTS and candidate.is_file():
                    self.validate_screenshot(str(candidate))
                    return str(candidate)
            return None

        if isinstance(data, Image.Image):
            if data.width <= 0 or data.height <= 0:
                raise ScreenshotError("The clipboard image is empty.")
            handle, temp_path = tempfile.mkstemp(
                prefix="screenshot_ai_", suffix=".png"
            )
            os.close(handle)
            try:
                image = data.convert("RGBA") if data.mode not in ("RGB", "RGBA") else data
                image.save(temp_path, format="PNG")
            except Exception as exc:  # noqa: BLE001
                remove_temp_file(temp_path)
                raise ScreenshotError(
                    f"Could not save the clipboard image: {exc}"
                ) from exc
            return temp_path

        return None

    # --------------------------------------------------------------- watching --
    def start_monitoring(
        self,
        folder_paths: Union[str, Sequence[str]],
        callback: Callable[[str], None],
    ) -> None:
        """Watch one or more folders; ``callback`` runs on a worker thread."""
        if isinstance(folder_paths, (str, os.PathLike)):
            folders = [Path(folder_paths)]
        else:
            folders = [Path(folder) for folder in folder_paths]

        if not folders:
            raise ScreenshotError("No folders to watch.")

        for folder in folders:
            if not folder.exists():
                raise ScreenshotError(f"Folder does not exist: {folder}")
            if not folder.is_dir():
                raise ScreenshotError(f"Not a directory: {folder}")

        self.stop_monitoring()
        self._callback = callback
        handler = _ScreenshotEventHandler(callback, self.processed_hashes, self._lock)
        self.observer = Observer()
        for folder in folders:
            self.observer.schedule(handler, str(folder), recursive=False)
        self.observer.start()

    def stop_monitoring(self) -> None:
        observer = self.observer
        self.observer = None
        self._callback = None
        if observer is not None:
            observer.stop()
            observer.join(timeout=3)

    @property
    def is_monitoring(self) -> bool:
        return self.observer is not None

    # ------------------------------------------------------------------ misc --
    def list_unprocessed(self, folder_path: str, limit: int = 10) -> List[str]:
        """Newest supported images in a folder that were not handled yet."""
        folder = Path(folder_path)
        if not folder.is_dir():
            return []
        candidates = [
            entry
            for entry in folder.iterdir()
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTS
        ]

        def mtime(entry: Path) -> float:
            try:
                return entry.stat().st_mtime
            except OSError:
                return 0.0

        candidates.sort(key=mtime, reverse=True)
        return [
            str(entry)
            for entry in candidates
            if not self.is_already_processed(str(entry))
        ][:limit]


def _wait_until_stable(path: str, timeout: float = 1.5) -> bool:
    """Wait until a freshly created file stops growing, so Pillow can open it."""
    deadline = time.monotonic() + timeout
    last_size = -1
    while time.monotonic() < deadline:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size > 0 and size == last_size:
            return True
        last_size = size
        time.sleep(0.1)
    return last_size > 0


class _ScreenshotEventHandler(FileSystemEventHandler):
    def __init__(self, callback, processed_hashes, lock):
        self.callback = callback
        self._processed_hashes = processed_hashes
        self._lock = lock
        self._seen = set()

    def _handle(self, path: str) -> None:
        if not path:
            return
        if Path(path).suffix.lower() not in SUPPORTED_EXTS:
            return
        if not _wait_until_stable(path):
            return
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception:  # noqa: BLE001 - ignore half-written/unsupported files
            return

        try:
            digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            return
        with self._lock:
            if digest in self._processed_hashes or digest in self._seen:
                return
            self._seen.add(digest)

        try:
            self.callback(path)
        except Exception:  # noqa: BLE001 - never let the watcher thread die
            pass

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._handle(event.dest_path)


# Convenience instance shared by the UI
screenshot_service = ScreenshotService()


def common_screenshot_folders() -> List[str]:
    """Existing folders where the Windows Snipping Tool commonly saves snips."""
    home = Path.home()
    candidates = [
        home / "Pictures" / "Screenshots",
        home / "Desktop",
    ]

    for env_name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        root = os.getenv(env_name)
        if root:
            candidates.append(Path(root) / "Pictures" / "Screenshots")

    seen = set()
    folders: List[str] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen or not resolved.is_dir():
            continue
        seen.add(key)
        folders.append(str(resolved))
    return folders


def remove_temp_file(file_path: Optional[str]) -> None:
    """Delete a temporary clipboard image, but never a normal user file."""
    if not file_path:
        return
    try:
        path = Path(file_path).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
    except OSError:
        return
    if temp_root not in path.parents:
        return
    if not path.name.startswith("screenshot_ai_"):
        return
    try:
        path.unlink()
    except OSError:
        pass

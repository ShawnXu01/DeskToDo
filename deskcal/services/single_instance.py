"""DeskToDo 单实例锁与本地进程通信。"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QLockFile, QObject, QStandardPaths, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "DeskToDo-8F2C9C9C-2B9B-4B3C-9B2A"
OPEN_SETTINGS_COMMAND = b"open-settings"


class SingleInstance(QObject):
    open_settings_requested = pyqtSignal()

    def __init__(self, server_name: str = SERVER_NAME, parent=None):
        super().__init__(parent)
        self._server_name = server_name
        lock_path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))
        self._lock = QLockFile(str(lock_path / f"{server_name}.lock"))
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connections)
        self._clients: set[QLocalSocket] = set()

    def become_primary(self) -> bool:
        if not self._lock.tryLock(100):
            return False

        QLocalServer.removeServer(self._server_name)
        if not self._server.listen(self._server_name):
            self._lock.unlock()
            raise OSError(self._server.errorString())
        return True

    def request_open_settings(self) -> bool:
        for _attempt in range(4):
            socket = QLocalSocket()
            socket.connectToServer(self._server_name)
            if not socket.waitForConnected(500):
                continue
            queued = socket.write(OPEN_SETTINGS_COMMAND)
            socket.flush()
            sent = queued == len(OPEN_SETTINGS_COMMAND) and (
                socket.bytesToWrite() == 0 or socket.waitForBytesWritten(1_000)
            )
            socket.disconnectFromServer()
            return sent
        return False

    def close(self) -> None:
        self._server.close()
        if self._lock.isLocked():
            self._lock.unlock()

    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            self._clients.add(socket)
            socket.readyRead.connect(lambda current=socket: self._read_command(current))
            socket.disconnected.connect(lambda current=socket: self._drop_client(current))
            self._read_command(socket)

    def _read_command(self, socket: QLocalSocket) -> None:
        if bytes(socket.readAll()).strip() == OPEN_SETTINGS_COMMAND:
            self.open_settings_requested.emit()

    def _drop_client(self, socket: QLocalSocket) -> None:
        self._clients.discard(socket)
        socket.deleteLater()

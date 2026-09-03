import uuid
from threading import Thread

from PyQt6.QtCore import QCoreApplication

from deskcal.services.single_instance import SingleInstance


def test_second_instance_can_request_settings_from_primary():
    app = QCoreApplication.instance() or QCoreApplication([])
    server_name = f"DeskToDo-test-{uuid.uuid4()}"
    primary = SingleInstance(server_name)
    secondary = SingleInstance(server_name)
    received = []
    primary.open_settings_requested.connect(lambda: received.append(True))

    try:
        assert primary.become_primary() is True
        assert secondary.become_primary() is False
        send_results = []
        sender = Thread(target=lambda: send_results.append(secondary.request_open_settings()))
        sender.start()

        while sender.is_alive():
            app.processEvents()
            sender.join(0.05)
        app.processEvents()

        assert send_results == [True]
        assert received == [True]
    finally:
        secondary.close()
        primary.close()

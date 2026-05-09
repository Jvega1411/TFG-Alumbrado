import pytest
import socket
from unittest.mock import Mock, patch
from fins.client import FINSClient
from config.settings import Config


class TestFINSClientConnect:

    @patch('fins.client.socket.socket')
    def test_connect_creates_udp_socket(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        FINSClient().connect()
        mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)

    @patch('fins.client.socket.socket')
    def test_connect_sets_timeout(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        FINSClient().connect()
        mock_socket_instance.settimeout.assert_called_once_with(Config.UDP_TIMEOUT)

    @patch('fins.client.socket.socket')
    def test_connect_binds_to_local_port(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        FINSClient().connect()
        mock_socket_instance.bind.assert_called_once_with(('', Config.UDP_LOCAL_PORT))

    @patch('fins.client.socket.socket')
    def test_connect_closes_existing_socket(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        client = FINSClient()
        client.connect()
        client.connect()
        assert mock_socket_instance.close.call_count == 1


class TestFINSClientClose:

    @patch('fins.client.socket.socket')
    def test_close_closes_socket(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        client = FINSClient()
        client.connect()
        client.close()
        mock_socket_instance.close.assert_called_once()
        assert client.socket is None

    def test_close_without_socket_does_not_fail(self):
        FINSClient().close()


class TestFINSClientContextManager:

    @patch('fins.client.socket.socket')
    def test_context_manager_connects_and_closes(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        with FINSClient() as client:
            assert client.socket is not None
        mock_socket_instance.close.assert_called_once()


class TestFINSClientReadMemoryArea:

    def test_read_memory_area_fails_without_connection(self):
        with pytest.raises(RuntimeError, match="Cliente no conectado"):
            FINSClient().read_memory_area('DM', 116, 1)

    @patch('fins.client.socket.socket')
    def test_read_memory_area_validates_response_origin(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        mock_socket_instance.recvfrom.return_value = (b'\x00' * 14, ('192.168.1.99', 9600))
        client = FINSClient()
        client.connect()
        with pytest.raises(ValueError, match="IP inesperada"):
            client.read_memory_area('DM', 116, 1)

import socket
from unittest.mock import Mock, patch

import pytest

from config.settings import Config
from fins.client import FINSClient
from fins.frame import FINSProtocolError, FINSResponseError, PLCNotInRunError


def _make_response(words=None, mres=0x00, sres=0x00, sid=1):
    payload = b""
    for word in words or []:
        payload += bytes([(word >> 8) & 0xFF, word & 0xFF])
    return (
        b"\x80\x00\x02\x00\x00\x00\x00\x00\x00"
        + bytes([sid])
        + b"\x01\x01"
        + bytes([mres, sres])
        + payload
    )


class TestFINSClientConnect:

    @patch("fins.client.socket.socket")
    def test_connect_creates_udp_socket(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        FINSClient().connect()
        mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)

    @patch("fins.client.socket.socket")
    def test_connect_sets_timeout(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        FINSClient().connect()
        mock_socket_instance.settimeout.assert_called_once_with(Config.UDP_TIMEOUT)

    @patch("fins.client.socket.socket")
    def test_connect_binds_to_local_port(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        FINSClient().connect()
        mock_socket_instance.bind.assert_called_once_with(("", Config.UDP_LOCAL_PORT))

    @patch("fins.client.socket.socket")
    def test_connect_closes_existing_socket(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        client = FINSClient()
        client.connect()
        client.connect()
        assert mock_socket_instance.close.call_count == 1


class TestFINSClientClose:

    @patch("fins.client.socket.socket")
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

    @patch("fins.client.socket.socket")
    def test_context_manager_connects_and_closes(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        with FINSClient() as client:
            assert client.socket is not None
        mock_socket_instance.close.assert_called_once()


class TestFINSClientReadMemoryArea:

    def test_read_memory_area_fails_without_connection(self):
        with pytest.raises(RuntimeError, match="Cliente no conectado"):
            FINSClient().read_memory_area("DM", 116, 1)

    @patch("fins.client.socket.socket")
    def test_read_memory_area_validates_response_origin(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        mock_socket_instance.recvfrom.return_value = (
            _make_response(words=[0], sid=1),
            ("192.168.1.99", 9600),
        )
        client = FINSClient()
        client.connect()
        with pytest.raises(ValueError, match="IP inesperada"):
            client.read_memory_area("DM", 116, 1)

    @patch("fins.client.socket.socket")
    def test_read_memory_area_returns_parsed_success(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        mock_socket_instance.recvfrom.return_value = (
            _make_response(words=[1, 13], sid=1),
            (Config.PLC_IP, 9600),
        )
        client = FINSClient()
        client.connect()
        result = client.read_memory_area("DM", 116, 2)
        assert result["success"] is True
        assert result["data"] == b"\x00\x01\x00\x0D"

    @patch("fins.client.socket.socket")
    def test_read_memory_area_sends_incrementing_sid(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        mock_socket_instance.recvfrom.side_effect = [
            (_make_response(words=[1], sid=1), (Config.PLC_IP, 9600)),
            (_make_response(words=[2], sid=2), (Config.PLC_IP, 9600)),
        ]
        client = FINSClient()
        client.connect()
        client.read_memory_area("DM", 116, 1)
        client.read_memory_area("DM", 116, 1)

        first_packet = mock_socket_instance.sendto.call_args_list[0][0][0]
        second_packet = mock_socket_instance.sendto.call_args_list[1][0][0]
        assert first_packet[9] == 1
        assert second_packet[9] == 2

    @patch("fins.client.socket.socket")
    def test_read_memory_area_sid_wraps_to_one(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        mock_socket_instance.recvfrom.return_value = (
            _make_response(words=[1], sid=1),
            (Config.PLC_IP, 9600),
        )
        client = FINSClient()
        client.connect()
        client._sid = 255
        client.read_memory_area("DM", 116, 1)

        sent_packet = mock_socket_instance.sendto.call_args[0][0]
        assert sent_packet[9] == 1

    @patch("fins.client.socket.socket")
    def test_read_memory_area_rejects_mismatched_sid(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        mock_socket_instance.recvfrom.return_value = (
            _make_response(words=[1], sid=2),
            (Config.PLC_IP, 9600),
        )
        client = FINSClient()
        client.connect()
        with pytest.raises(FINSProtocolError, match="SID inesperado"):
            client.read_memory_area("DM", 116, 1)

    @patch("fins.client.socket.socket")
    def test_read_memory_area_raises_plc_not_run(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        mock_socket_instance.recvfrom.return_value = (
            _make_response(mres=0x21, sres=0x08, sid=1),
            (Config.PLC_IP, 9600),
        )
        client = FINSClient()
        client.connect()
        with pytest.raises(PLCNotInRunError):
            client.read_memory_area("DM", 116, 1)

    @patch("fins.client.socket.socket")
    def test_read_memory_area_raises_fins_response_error(self, mock_socket_class):
        mock_socket_instance = Mock()
        mock_socket_class.return_value = mock_socket_instance
        mock_socket_instance.recvfrom.return_value = (
            _make_response(mres=0x11, sres=0x00, sid=1),
            (Config.PLC_IP, 9600),
        )
        client = FINSClient()
        client.connect()
        with pytest.raises(FINSResponseError):
            client.read_memory_area("DM", 116, 1)

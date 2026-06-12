import json
from unittest.mock import Mock, call, patch

import pytest

from acquisition.publisher import _payloads_equal, _publish_payload, main, run_publisher
from tests.v3_helpers import sample_payload_dict, sample_variables


class TestPayloadsEqual:
    def test_equal_payloads_ignore_ts_and_clocks(self):
        a = sample_payload_dict()
        b = sample_payload_dict()
        b["ts"] = "2026-05-12T08:30:02+00:00"
        b["plc_reloj"]["decoded"]["segundo"] = 2
        b["reloj_ar"]["decoded"]["segundo"] = 2
        b["contexto_plc_raw"]["ranges"][6]["raw_words"][0] = 2
        b["contexto_plc_raw"]["ranges"][10]["raw_words"][0] = 0x3002
        assert _payloads_equal(a, b) is True

    def test_payload_change_not_equal(self):
        a = sample_payload_dict()
        b = sample_payload_dict()
        b["modo"]["modfunalu"] = 1
        b["modo"]["modo_label"] = "fotocelula"
        assert _payloads_equal(a, b) is False

    def test_context_raw_non_clock_change_not_equal(self):
        a = sample_payload_dict()
        b = sample_payload_dict()
        b["contexto_plc_raw"]["ranges"][3]["raw_words"][0] = 0
        assert _payloads_equal(a, b) is False


class TestRunPublisher:
    def _mock_fins(self):
        mock_fins = Mock()
        mock_fins.__enter__ = Mock(return_value=mock_fins)
        mock_fins.__exit__ = Mock(return_value=False)
        return mock_fins

    def _mock_publish_success(self):
        mock_msg_info = Mock()
        mock_msg_info.rc = 0
        mock_msg_info.is_published.return_value = True
        return mock_msg_info

    def test_publishes_on_first_run(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch("acquisition.publisher.Config.validate_publisher"), \
             patch("acquisition.publisher.mqtt.Client", return_value=mock_mqtt), \
             patch("acquisition.publisher.FINSClient", return_value=self._mock_fins()), \
             patch("acquisition.publisher.read_all_variables", return_value=sample_variables()):
            run_publisher(max_cycles=1)

        mock_mqtt.publish.assert_called_once()

    def test_does_not_publish_when_unchanged(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch("acquisition.publisher.Config.validate_publisher"), \
             patch("acquisition.publisher.mqtt.Client", return_value=mock_mqtt), \
             patch("acquisition.publisher.FINSClient", return_value=self._mock_fins()), \
             patch("acquisition.publisher.read_all_variables", return_value=sample_variables()), \
             patch("acquisition.publisher.time.monotonic", return_value=0.0):
            run_publisher(max_cycles=2)

        assert mock_mqtt.publish.call_count == 1

    def test_publishes_after_heartbeat_interval(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch("acquisition.publisher.Config.validate_publisher"), \
             patch("acquisition.publisher.Config.HEARTBEAT_INTERVAL_S", 30.0), \
             patch("acquisition.publisher.mqtt.Client", return_value=mock_mqtt), \
             patch("acquisition.publisher.FINSClient", return_value=self._mock_fins()), \
             patch("acquisition.publisher.read_all_variables", return_value=sample_variables()), \
             patch("acquisition.publisher.time.monotonic", side_effect=[0.0, 0.0, 31.0, 31.0]):
            run_publisher(max_cycles=2)

        assert mock_mqtt.publish.call_count == 2

    def test_publishes_on_fins_error(self):
        from fins.frame import FINSError

        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch("acquisition.publisher.Config.validate_publisher"), \
             patch("acquisition.publisher.mqtt.Client", return_value=mock_mqtt), \
             patch("acquisition.publisher.FINSClient", return_value=self._mock_fins()), \
             patch("acquisition.publisher.read_all_variables", side_effect=FINSError("timeout")):
            run_publisher(max_cycles=1)

        published_payload = json.loads(mock_mqtt.publish.call_args[0][1])
        assert published_payload["schema_version"] == 3
        assert published_payload["fins_ok"] is False

    def test_publish_failure_does_not_update_last_payload(self):
        mock_msg_info = Mock()
        mock_msg_info.rc = 4
        mock_msg_info.is_published.return_value = False
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = mock_msg_info

        with patch("acquisition.publisher.Config.validate_publisher"), \
             patch("acquisition.publisher.mqtt.Client", return_value=mock_mqtt), \
             patch("acquisition.publisher.FINSClient", return_value=self._mock_fins()), \
             patch("acquisition.publisher.read_all_variables", return_value=sample_variables()), \
             patch("acquisition.publisher.time.monotonic", return_value=0.0):
            run_publisher(max_cycles=2)

        assert mock_mqtt.publish.call_count == 2

    def test_publish_payload_returns_false_when_publish_raises(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.side_effect = RuntimeError("no connection")
        assert _publish_payload(mock_mqtt, {"fins_ok": True}) is False

    def test_connect_failure_does_not_read_fins_or_publish(self):
        mock_mqtt = Mock()
        mock_mqtt.connect.side_effect = OSError("broker unavailable")
        mock_fins_cls = Mock()
        mock_read = Mock()

        with patch("acquisition.publisher.Config.validate_publisher"), \
             patch("acquisition.publisher.mqtt.Client", return_value=mock_mqtt), \
             patch("acquisition.publisher.FINSClient", mock_fins_cls), \
             patch("acquisition.publisher.read_all_variables", mock_read):
            with pytest.raises(OSError, match="broker unavailable"):
                run_publisher(max_cycles=1)

        mock_mqtt.loop_start.assert_not_called()
        mock_mqtt.publish.assert_not_called()
        mock_fins_cls.assert_not_called()
        mock_read.assert_not_called()

    def test_sets_mqtt_credentials_before_connect(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch("acquisition.publisher.Config.validate_publisher"), \
             patch("acquisition.publisher.Config.MQTT_USERNAME", "gwpub"), \
             patch("acquisition.publisher.Config.MQTT_PASSWORD", "test-password"), \
             patch("acquisition.publisher.mqtt.Client", return_value=mock_mqtt), \
             patch("acquisition.publisher.FINSClient", return_value=self._mock_fins()), \
             patch("acquisition.publisher.read_all_variables", return_value=sample_variables()):
            run_publisher(max_cycles=1)

        mock_mqtt.username_pw_set.assert_called_once_with("gwpub", "test-password")
        connect_call = next(c for c in mock_mqtt.method_calls if c[0] == "connect")
        assert mock_mqtt.method_calls.index(call.username_pw_set("gwpub", "test-password")) < \
            mock_mqtt.method_calls.index(connect_call)

    def test_main_accepts_max_cycles_argument(self):
        with patch("acquisition.publisher.run_publisher") as mock_run:
            main(["--max-cycles", "1"])

        mock_run.assert_called_once_with(max_cycles=1)

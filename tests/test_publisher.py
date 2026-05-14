import json
import pytest
from unittest.mock import Mock, call, patch

from acquisition.publisher import _payloads_equal, _publish_payload, run_publisher


class TestPayloadsEqual:

    def _payload(self, modfunalu=0, sec1_auto=False) -> dict:
        secciones = [
            {
                'id': i + 1,
                'automatico': False,
                'manual': False,
                'horario_activo': False,
            }
            for i in range(112)
        ]
        secciones[0]['automatico'] = sec1_auto
        return {
            'ts': '2026-05-12T08:30:00+00:00',
            'fins_ok': True,
            'fins_error': None,
            'plc_reloj': {
                'seg': 0,
                'min': 30,
                'hora': 8,
                'dia': 12,
                'mes': 5,
                'anio': 2026,
                'diasem': 2,
            },
            'modo': {
                'modfunalu': modfunalu,
                'fotocelula_entrada': False,
                'fotocelula_mem_fun': False,
                'fotocelula_mem_act': False,
            },
            'secciones': secciones,
            'horarios': {'raw_words': [0] * 28},
            'diagnostico': {
                'cycle_time_error': False,
                'low_battery': False,
                'io_verify_error': False,
            },
            'read_status': {
                'secciones': {'status': 'ok', 'error': None},
                'modo': {'status': 'ok', 'error': None},
                'fotocelula': {'status': 'ok', 'error': None},
                'reloj': {'status': 'ok', 'error': None},
                'horarios': {'status': 'ok', 'error': None},
                'diagnostico': {'status': 'ok', 'error': None},
            },
        }

    def test_equal_payloads_ignores_ts(self):
        a = self._payload()
        b = self._payload()
        b['ts'] = '2026-05-12T08:30:10+00:00'
        assert _payloads_equal(a, b) is True

    def test_different_modfunalu_not_equal(self):
        a = self._payload(modfunalu=0)
        b = self._payload(modfunalu=1)
        assert _payloads_equal(a, b) is False

    def test_different_seccion_state_not_equal(self):
        a = self._payload(sec1_auto=False)
        b = self._payload(sec1_auto=True)
        assert _payloads_equal(a, b) is False

    def test_same_seccion_states_equal(self):
        a = self._payload(sec1_auto=True)
        b = self._payload(sec1_auto=True)
        b['ts'] = '2099-01-01T00:00:00+00:00'
        assert _payloads_equal(a, b) is True

    def test_equal_payloads_ignores_plc_reloj(self):
        a = self._payload()
        b = self._payload()
        b['plc_reloj']['seg'] = 59
        b['plc_reloj']['min'] = 31
        assert _payloads_equal(a, b) is True

    def test_error_payload_not_equal_to_ok(self):
        ok = self._payload()
        err = {
            'ts': '2026-05-12T08:30:00+00:00',
            'fins_ok': False,
            'fins_error': 'timeout',
            'read_status': {
                'secciones': {'status': 'failed', 'error': 'timeout'},
                'modo': {'status': 'failed', 'error': 'timeout'},
                'fotocelula': {'status': 'failed', 'error': 'timeout'},
                'reloj': {'status': 'failed', 'error': 'timeout'},
                'horarios': {'status': 'failed', 'error': 'timeout'},
                'diagnostico': {'status': 'failed', 'error': 'timeout'},
            },
        }
        assert _payloads_equal(ok, err) is False


class TestRunPublisher:

    def _base_vars(self, plc_seg=0):
        return {
            'secciones': [
                {
                    'id': i + 1,
                    'automatico': False,
                    'manual': False,
                    'horario_activo': False,
                }
                for i in range(112)
            ],
            'modfunalu': 0,
            'fotocelula_entrada': False,
            'fotocelula_mem_fun': False,
            'fotocelula_mem_act': False,
            'plc_seg': plc_seg,
            'plc_min': 0,
            'plc_hora': 0,
            'plc_dia': 1,
            'plc_mes': 1,
            'plc_anio': 2026,
            'plc_diasem': 1,
            'horarios_raw': [0] * 28,
            'cycle_time_error': False,
            'low_battery': False,
            'io_verify_error': False,
            'read_status': {
                'secciones': {'status': 'ok', 'error': None},
                'modo': {'status': 'ok', 'error': None},
                'fotocelula': {'status': 'ok', 'error': None},
                'reloj': {'status': 'ok', 'error': None},
                'horarios': {'status': 'ok', 'error': None},
                'diagnostico': {'status': 'ok', 'error': None},
            },
        }

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

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()):
            run_publisher(max_cycles=1)

        mock_mqtt.publish.assert_called_once()

    def test_does_not_publish_when_unchanged(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()), \
             patch('acquisition.publisher.time.monotonic', return_value=0.0):
            run_publisher(max_cycles=2)

        assert mock_mqtt.publish.call_count == 1

    def test_publishes_unchanged_payload_after_heartbeat_interval(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.Config.HEARTBEAT_INTERVAL_S', 300.0), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()), \
             patch('acquisition.publisher.time.monotonic', side_effect=[0.0, 0.0, 301.0, 301.0]):
            run_publisher(max_cycles=2)

        assert mock_mqtt.publish.call_count == 2

    def test_does_not_publish_when_only_plc_reloj_changes(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', side_effect=[
                 self._base_vars(plc_seg=1),
                 self._base_vars(plc_seg=2),
             ]), \
             patch('acquisition.publisher.time.monotonic', return_value=0.0):
            run_publisher(max_cycles=2)

        assert mock_mqtt.publish.call_count == 1

    def test_publishes_on_fins_error(self):
        from fins.frame import FINSError

        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', side_effect=FINSError('timeout')):
            run_publisher(max_cycles=1)

        assert mock_mqtt.publish.call_count == 1
        published_payload = json.loads(mock_mqtt.publish.call_args[0][1])
        assert published_payload['fins_ok'] is False

    def test_publish_failure_does_not_update_last_payload(self):
        mock_msg_info = Mock()
        mock_msg_info.rc = 4
        mock_msg_info.is_published.return_value = False

        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = mock_msg_info

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()), \
             patch('acquisition.publisher.time.monotonic', return_value=0.0):
            run_publisher(max_cycles=2)

        assert mock_mqtt.publish.call_count == 2

    def test_publish_payload_returns_false_when_publish_raises(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.side_effect = RuntimeError('no connection')
        assert _publish_payload(mock_mqtt, {'fins_ok': True}) is False

    def test_publish_raises_does_not_update_last_payload_and_retries_next_cycle(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.side_effect = [RuntimeError('no connection'), self._mock_publish_success()]

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()), \
             patch('acquisition.publisher.time.monotonic', return_value=0.0):
            run_publisher(max_cycles=2)

        assert mock_mqtt.publish.call_count == 2

    def test_connect_failure_does_not_read_fins_or_publish(self):
        mock_mqtt = Mock()
        mock_mqtt.connect.side_effect = OSError('broker unavailable')
        mock_fins_cls = Mock()
        mock_read = Mock()

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', mock_fins_cls), \
             patch('acquisition.publisher.read_all_variables', mock_read):
            with pytest.raises(OSError, match='broker unavailable'):
                run_publisher(max_cycles=1)

        mock_mqtt.loop_start.assert_not_called()
        mock_mqtt.publish.assert_not_called()
        mock_fins_cls.assert_not_called()
        mock_read.assert_not_called()

    def test_sets_mqtt_credentials_before_connect_when_username_configured(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.Config.MQTT_USERNAME', 'gwpub'), \
             patch('acquisition.publisher.Config.MQTT_PASSWORD', 'test-password'), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()):
            run_publisher(max_cycles=1)

        mock_mqtt.username_pw_set.assert_called_once_with('gwpub', 'test-password')
        connect_call = next(c for c in mock_mqtt.method_calls if c[0] == 'connect')
        assert mock_mqtt.method_calls.index(call.username_pw_set('gwpub', 'test-password')) < \
            mock_mqtt.method_calls.index(connect_call)

    def test_does_not_set_mqtt_credentials_when_username_empty(self):
        mock_mqtt = Mock()
        mock_mqtt.publish.return_value = self._mock_publish_success()

        with patch('acquisition.publisher.Config.validate_publisher'), \
             patch('acquisition.publisher.Config.MQTT_USERNAME', ''), \
             patch('acquisition.publisher.Config.MQTT_PASSWORD', ''), \
             patch('acquisition.publisher.mqtt.Client', return_value=mock_mqtt), \
             patch('acquisition.publisher.FINSClient', return_value=self._mock_fins()), \
             patch('acquisition.publisher.read_all_variables', return_value=self._base_vars()):
            run_publisher(max_cycles=1)

        mock_mqtt.username_pw_set.assert_not_called()

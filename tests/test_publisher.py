import json
from unittest.mock import Mock, patch

from acquisition.publisher import _payloads_equal, run_publisher


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

    def test_error_payload_not_equal_to_ok(self):
        ok = self._payload()
        err = {
            'ts': '2026-05-12T08:30:00+00:00',
            'fins_ok': False,
            'fins_error': 'timeout',
        }
        assert _payloads_equal(ok, err) is False


class TestRunPublisher:

    def _base_vars(self):
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
            'plc_seg': 0,
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

import pytest
from unittest.mock import patch
from config.settings import Config


class TestConfigParseInt:

    def test_parse_decimal(self):
        assert Config._parse_int('0') == 0
        assert Config._parse_int('10') == 10
        assert Config._parse_int('255') == 255

    def test_parse_hexadecimal_lowercase(self):
        assert Config._parse_int('0x00') == 0
        assert Config._parse_int('0x0a') == 10
        assert Config._parse_int('0xff') == 255

    def test_parse_hexadecimal_uppercase(self):
        assert Config._parse_int('0X00') == 0
        assert Config._parse_int('0X0A') == 10
        assert Config._parse_int('0XFF') == 255

    def test_parse_with_whitespace(self):
        assert Config._parse_int('  10  ') == 10
        assert Config._parse_int('  0xff  ') == 255


class TestConfigValidation:

    def test_config_defaults_on_import(self):
        assert Config.PLC_IP == '192.168.250.1'
        assert Config.PLC_PORT == 9600
        assert Config.UDP_LOCAL_PORT == 9600
        assert Config.UDP_TIMEOUT == 2.0

    def test_fins_parameters_in_valid_range(self):
        for attr in [
            'FINS_SOURCE_NETWORK', 'FINS_SOURCE_NODE', 'FINS_SOURCE_UNIT',
            'FINS_DEST_NETWORK',   'FINS_DEST_NODE',   'FINS_DEST_UNIT',
        ]:
            assert 0 <= getattr(Config, attr) <= 255

    def test_timeout_positive(self):
        assert Config.UDP_TIMEOUT > 0

    def test_ports_in_valid_range(self):
        assert 1 <= Config.PLC_PORT <= 65535
        assert 1 <= Config.UDP_LOCAL_PORT <= 65535

    def test_db_and_acquisition_defaults(self):
        assert Config.DB_PORT == 1433
        assert Config.ACQUISITION_INTERVAL_S == 10.0
        assert Config.ACQUISITION_INTERVAL_S > 0

    def test_db_estados_url_default_is_sqlite(self):
        assert Config.DB_ESTADOS_URL.startswith('sqlite:///')
        assert 'bd_estados.db' in Config.DB_ESTADOS_URL

    def test_db_hist_url_default_is_sqlite(self):
        assert Config.DB_HIST_URL.startswith('sqlite:///')
        assert 'bd_historizacion.db' in Config.DB_HIST_URL


class TestMqttDefaults:

    def test_mqtt_broker_host_default_is_empty(self):
        assert Config.MQTT_BROKER_HOST == ''

    def test_mqtt_broker_port_default(self):
        assert Config.MQTT_BROKER_PORT == 1883

    def test_mqtt_topic_default(self):
        assert Config.MQTT_TOPIC == 'alumbrado/estado'

    def test_mqtt_client_id_default(self):
        assert Config.MQTT_CLIENT_ID == 'alumbrado-publisher'

    def test_mqtt_username_default_is_empty(self):
        assert Config.MQTT_USERNAME == ''

    def test_mqtt_password_default_is_empty(self):
        assert Config.MQTT_PASSWORD == ''

    def test_heartbeat_interval_default(self):
        assert Config.HEARTBEAT_INTERVAL_S == 300.0

    def test_acquisition_interval_default_is_10(self):
        assert Config.ACQUISITION_INTERVAL_S == 10.0

    def test_api_host_default_is_localhost(self):
        assert Config.API_HOST == '127.0.0.1'

    def test_api_port_default(self):
        assert Config.API_PORT == 8000

    def test_db_auto_create_default_is_false(self):
        assert Config.DB_AUTO_CREATE is False


class TestValidatePublisher:

    def test_validate_publisher_fails_if_mqtt_broker_host_empty(self):
        with patch.object(Config, 'MQTT_BROKER_HOST', ''):
            with pytest.raises(ValueError, match='MQTT_BROKER_HOST'):
                Config.validate_publisher()

    def test_validate_publisher_passes_with_broker_host(self):
        with patch.object(Config, 'MQTT_BROKER_HOST', '10.0.0.1'):
            Config.validate_publisher()  # must not raise

    def test_validate_publisher_allows_empty_mqtt_auth(self):
        with patch.object(Config, 'MQTT_BROKER_HOST', '10.0.0.1'), \
             patch.object(Config, 'MQTT_USERNAME', ''), \
             patch.object(Config, 'MQTT_PASSWORD', ''):
            Config.validate_publisher()

    def test_validate_publisher_rejects_password_without_username(self):
        with patch.object(Config, 'MQTT_BROKER_HOST', '10.0.0.1'), \
             patch.object(Config, 'MQTT_USERNAME', ''), \
             patch.object(Config, 'MQTT_PASSWORD', 'secret'):
            with pytest.raises(ValueError, match='MQTT_USERNAME'):
                Config.validate_publisher()


class TestValidateApi:

    def test_validate_api_passes_without_mqtt_broker_host(self):
        with patch.object(Config, 'DB_ESTADOS_URL', 'sqlite:///x.db'):
            Config.validate_api()  # must not raise — does not require MQTT

    def test_validate_api_fails_if_db_estados_url_empty(self):
        with patch.object(Config, 'DB_ESTADOS_URL', ''):
            with pytest.raises(ValueError, match='DB_ESTADOS_URL'):
                Config.validate_api()

    def test_validate_api_fails_if_api_host_empty(self):
        with patch.object(Config, 'DB_ESTADOS_URL', 'sqlite:///x.db'), \
             patch.object(Config, 'API_HOST', ''):
            with pytest.raises(ValueError, match='API_HOST'):
                Config.validate_api()


class TestValidateSubscriber:

    def test_validate_subscriber_does_not_require_fins_config(self):
        with patch.object(Config, 'DB_ESTADOS_URL', 'sqlite:///x.db'), \
             patch.object(Config, 'MQTT_BROKER_HOST', '10.0.0.1'):
            Config.validate_subscriber()  # must not raise

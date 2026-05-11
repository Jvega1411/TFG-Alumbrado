import pytest
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
        assert Config.ACQUISITION_INTERVAL_S == 30.0
        assert Config.ACQUISITION_INTERVAL_S > 0

    def test_db_estados_url_default_is_sqlite(self):
        assert Config.DB_ESTADOS_URL.startswith('sqlite:///')
        assert 'bd_estados.db' in Config.DB_ESTADOS_URL

    def test_db_hist_url_default_is_sqlite(self):
        assert Config.DB_HIST_URL.startswith('sqlite:///')
        assert 'bd_historizacion.db' in Config.DB_HIST_URL

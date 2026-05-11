from acquisition.poller import extract_section_bits


class TestExtractSectionBits:

    def test_all_zeros_returns_false_for_all(self):
        words = [0] * 21
        result = extract_section_bits(words, 0)
        assert len(result) == 112
        assert all(v is False for v in result)

    def test_all_ones_returns_true_for_all(self):
        words = [0xFFFF] * 21
        result = extract_section_bits(words, 0)
        assert all(v is True for v in result)

    def test_section1_is_bit0_of_first_word(self):
        words = [0] * 21
        words[0] = 0x0001
        result = extract_section_bits(words, 0)
        assert result[0] is True
        assert result[1] is False

    def test_section16_is_bit15_of_first_word(self):
        words = [0] * 21
        words[0] = 0x8000
        result = extract_section_bits(words, 0)
        assert result[14] is False
        assert result[15] is True

    def test_section17_is_bit0_of_second_word(self):
        words = [0] * 21
        words[1] = 0x0001
        result = extract_section_bits(words, 0)
        assert result[15] is False
        assert result[16] is True

    def test_section112_is_bit15_of_seventh_word(self):
        words = [0] * 21
        words[6] = 0x8000
        result = extract_section_bits(words, 0)
        assert result[110] is False
        assert result[111] is True

    def test_group_offset_selects_correct_group(self):
        words = [0] * 21
        words[7] = 0x0001
        result_group0 = extract_section_bits(words, 0)
        result_group7 = extract_section_bits(words, 7)
        assert result_group0[0] is False
        assert result_group7[0] is True

    def test_returns_exactly_112_values(self):
        assert len(extract_section_bits([0] * 21, 0)) == 112
        assert len(extract_section_bits([0] * 21, 7)) == 112
        assert len(extract_section_bits([0] * 21, 14)) == 112

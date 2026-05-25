from model.json_columns import dump_json_column, load_json_column


def test_json_column_roundtrip_compact_text():
    text = dump_json_column({"raw": [1, 2], "source": "D1000"})

    assert text == '{"raw":[1,2],"source":"D1000"}'
    assert load_json_column(text) == {"raw": [1, 2], "source": "D1000"}


def test_json_column_preserves_none_and_loaded_values():
    assert dump_json_column(None) is None
    assert load_json_column(None) is None
    assert load_json_column([1, 2]) == [1, 2]

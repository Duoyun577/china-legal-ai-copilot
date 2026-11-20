"""Tests for the PostgreSQL row shim matching sqlite3.Row semantics."""

from utils.database import _Row, _compat_row_factory


class _Col:
    def __init__(self, name):
        self.name = name


class _Cursor:
    def __init__(self, columns):
        self.description = [_Col(c) for c in columns]


def test_row_supports_numeric_and_name_indexing():
    row = _Row(["a", "b"], [1, "x"])
    assert row[0] == 1
    assert row[1] == "x"
    assert row["a"] == 1
    assert row["b"] == "x"


def test_row_supports_iteration_and_unpacking():
    row = _Row(["a", "b"], [1, "x"])
    assert list(row) == [1, "x"]
    a, b = row
    assert (a, b) == (1, "x")


def test_row_supports_dict_and_keys():
    row = _Row(["a", "b"], [1, "x"])
    assert dict(row) == {"a": 1, "b": "x"}
    assert row.keys() == ["a", "b"]
    assert row.get("missing") is None


def test_row_factory_builds_row_per_cursor_description():
    factory = _compat_row_factory(_Cursor(["event_type", "cnt"]))
    row = factory(("consult", 3))
    assert isinstance(row, _Row)
    assert row[0] == "consult"
    assert row["cnt"] == 3
    assert tuple(row) == ("consult", 3)

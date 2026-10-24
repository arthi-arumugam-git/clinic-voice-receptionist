import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from scripts.export_csv import export_csv, safe_csv_cell
from store import SlotUnavailable, Store

START = datetime(2027, 1, 4, 15, tzinfo=UTC)


def book(store, call_id="call-1", starts_at=START, duration_minutes=60, **extra):
    return store.create_appointment(
        call_id=call_id,
        patient_name="Demo Patient",
        phone="+14155550100",
        service_id="cleaning",
        starts_at=starts_at,
        duration_minutes=duration_minutes,
        **extra,
    )


def test_persists_across_connections_and_summary_is_json_safe(tmp_path):
    db = tmp_path / "nested" / "clinic.sqlite3"
    with Store(db) as store:
        store.create_call("call-1")
        appointment = book(store)
        store.create_message(
            call_id="call-1", name="Demo Patient", phone="+14155550100", message="Please call back."
        )
        finished = store.finish_call("call-1", "completed", "Caller finished")
    with Store(db) as store:
        summary = store.get_call_summary("call-1")
        assert summary["call"] == finished
        assert summary["appointments"][0] == appointment
        assert len(summary["messages"]) == 1
        json.dumps(summary)


def test_call_and_request_retries_are_idempotent():
    with Store(":memory:") as store:
        first = store.create_call("call-1")
        assert store.create_call("call-1") == first
        assert book(store) == book(store)
        kwargs = dict(call_id="call-1", name="Demo", phone="5550100000", message="Call me")
        assert store.create_message(**kwargs) == store.create_message(**kwargs)
        ended = store.finish_call("call-1", "timeout", "Idle")
        assert store.finish_call("call-1", "disconnected") == ended
        assert len(store.list_appointments()) == 1
        assert len(store.list_messages()) == 1


@pytest.mark.parametrize("offset", [-30, 0, 30])
def test_full_duration_overlap_is_rejected(offset):
    with Store(":memory:") as store:
        store.create_call("call-1")
        store.create_call("call-2")
        book(store)
        with pytest.raises(SlotUnavailable):
            book(store, "call-2", START + timedelta(minutes=offset))


def test_back_to_back_requests_are_allowed():
    with Store(":memory:") as store:
        store.create_call("call-1")
        book(store)
        book(store, starts_at=START + timedelta(hours=1))
        assert len(store.list_appointments()) == 2


def test_cross_connection_race_reserves_only_one_slot(tmp_path):
    db = tmp_path / "clinic.sqlite3"
    with Store(db) as store:
        store.create_call("one")
        store.create_call("two")

    def reserve(call_id):
        with Store(db) as store:
            try:
                return book(store, call_id)["id"]
            except SlotUnavailable:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, ["one", "two"]))
    assert sum(result is not None for result in results) == 1


def test_call_summary_is_scoped_to_one_call():
    with Store(":memory:") as store:
        store.create_call("one")
        store.create_call("two")
        store.create_message(call_id="one", name="Demo", phone="5550100000", message="One")
        assert store.get_call_summary("two")["messages"] == []
        with pytest.raises(ValueError, match="unknown"):
            store.get_call_summary("missing")


def test_naive_datetime_is_rejected():
    with Store(":memory:") as store:
        store.create_call("call-1")
        with pytest.raises(ValueError, match="timezone-aware"):
            book(store, starts_at=datetime(2027, 1, 4, 15))


@pytest.mark.parametrize(
    "value",
    [
        '=HYPERLINK("bad")',
        "+15550100000",
        "-1+2",
        "@SUM(1)",
        "  =1+1",
        "\ttext",
        "\rtext",
        "\ntext",
    ],
)
def test_csv_formula_prefixes_are_neutralized(value):
    assert safe_csv_cell(value) == "'" + value


def test_csv_exports_headers_unicode_and_escaped_cells(tmp_path):
    with Store(":memory:") as store:
        store.create_call("call-1")
        store.create_message(call_id="call-1", name="Zoë", phone="+14155550100", message="=1+1")
        path = tmp_path / "messages.csv"
        assert export_csv(store, path, "messages") == 1
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert rows[0]["name"] == "Zoë"
        assert rows[0]["phone"] == "'+14155550100"
        assert rows[0]["message"] == "'=1+1"
        assert export_csv(store, tmp_path / "empty.csv") == 0
        assert "patient_name" in (tmp_path / "empty.csv").read_text(encoding="utf-8-sig")

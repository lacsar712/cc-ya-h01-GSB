"""worker 落库：结论必须与 judge 一致；写库中断必须整笔回滚不留半行。"""

import psycopg
import pytest

import worker
from tests.fakes import FakeConn


def _pending_row(row_id, err):
    return {
        "id": row_id,
        "turbine_code": f"W{row_id:02d}",
        "yaw_err_deg": err,
        "status": "pending",
        "verdict": None,
        "reason": None,
        "processed_at": None,
    }


@pytest.mark.parametrize(
    "err,expected",
    [
        (0.4, "合格"),
        (1.5, "合格"),
        (-1.5, "合格"),
        (3.2, "偏航超差"),
        (-1.6, "偏航超差"),
    ],
)
def test_persists_real_verdict(err, expected):
    conn = FakeConn(rows=[_pending_row(1, err)])
    assert worker.claim_and_process(conn) is True
    conn.commit()

    row = conn.committed[0]
    assert row["status"] == "done"
    assert row["verdict"] == expected
    assert row["processed_at"] is not None
    # 落库脚注必须是判定说明，不得残留旁路篡改文案
    assert "旁路" not in (row["reason"] or "")
    assert str(abs(err)) in row["reason"]


def test_no_pending_row_returns_false():
    conn = FakeConn(rows=[_pending_row(1, 0.4)])
    conn.committed[0]["status"] = "done"
    conn.committed[0]["verdict"] = "合格"
    assert worker.claim_and_process(conn) is False


def test_write_interruption_leaves_no_half_row():
    conn = FakeConn(rows=[_pending_row(7, 0.4)], fail_update=True)
    with pytest.raises(psycopg.Error):
        worker.claim_and_process(conn)

    # 事务回滚：仍是干净的 pending，没有任何半成品字段
    row = conn.committed[0]
    assert row["status"] == "pending"
    assert row["verdict"] is None
    assert row["reason"] is None
    assert row["processed_at"] is None
    assert conn.update_count == 1

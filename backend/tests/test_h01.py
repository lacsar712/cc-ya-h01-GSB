"""H01 链路回归：落库结论 → 列表数据 → 判定边界。"""

import asyncio
import importlib.util

import api
import worker
from rules import judge


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class FakeConn:
    """最小可用的连接替身：记录写库语句，回放预设查询结果。"""

    def __init__(self, claimed=None, returning=None, listed=None):
        self.claimed = claimed
        self.returning = returning
        self.listed = listed or []
        self.updates = []
        self.inserts = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def transaction(self):
        return self

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split()).lower()
        if "for update" in normalized:
            return FakeCursor(row=self.claimed)
        if normalized.startswith("update"):
            self.updates.append((sql, params))
            return FakeCursor()
        if normalized.startswith("insert"):
            self.inserts.append((sql, params))
            return FakeCursor(row=self.returning)
        if normalized.startswith("select count"):
            return FakeCursor(row={"n": 1})
        if normalized.startswith("select"):
            return FakeCursor(rows=self.listed)
        return FakeCursor()

    def commit(self):
        self.committed = True


# ---------- 判定边界：压线 ±1.5° 不得漂成超差，大偏差不得伪合格 ----------

def test_judge_boundary_inclusive():
    for err in (1.5, -1.5, 0.0, 0.4, -1.49):
        verdict, reason = judge(err)
        assert verdict == "合格", err
        assert "在 ±1.5° 以内" in reason


def test_judge_beyond_threshold():
    for err in (1.5000001, -1.5000001, 3.2, -9.9):
        verdict, reason = judge(err)
        assert verdict == "偏航超差", err
        assert "超过 ±1.5°" in reason


# ---------- 落库：worker 必须原样写入判定结论，同事务不留半行 ----------

def test_worker_saves_pass_verdict_verbatim():
    conn = FakeConn(claimed={"id": 1, "turbine_code": "W01", "yaw_err_deg": 0.4})
    assert worker.claim_and_process(conn) is True
    assert len(conn.updates) == 1
    sql, params = conn.updates[0]
    assert "status = 'done'" in sql
    verdict, reason, processed_at, row_id = params
    assert (verdict, row_id) == ("合格", 1)
    assert "在 ±1.5° 以内" in reason
    assert processed_at is not None


def test_worker_saves_fail_verdict_verbatim():
    conn = FakeConn(claimed={"id": 2, "turbine_code": "W07", "yaw_err_deg": 3.2})
    assert worker.claim_and_process(conn) is True
    _, params = conn.updates[0]
    assert params[0] == "偏航超差"
    assert "超过 ±1.5°" in params[1]


def test_worker_idle_when_nothing_pending():
    conn = FakeConn(claimed=None)
    assert worker.claim_and_process(conn) is False
    assert conn.updates == []


# ---------- 列表：接口必须按库中存储原样返回，不改结论/脚注/状态 ----------

def _token(username, role):
    from jose import jwt

    return jwt.encode({"sub": username, "role": role}, api.SECRET, algorithm="HS256")


def _stored_rows():
    return [
        {
            "id": 1, "turbine_code": "W01", "yaw_err_deg": 0.4,
            "status": "done", "verdict": "合格",
            "reason": "偏航误差 0.4° 在 ±1.5° 以内",
            "created_by": "technician",
            "created_at": None, "processed_at": None,
        },
        {
            "id": 2, "turbine_code": "W07", "yaw_err_deg": 3.2,
            "status": "done", "verdict": "偏航超差",
            "reason": "偏航误差 3.2° 超过 ±1.5°",
            "created_by": "technician",
            "created_at": None, "processed_at": None,
        },
    ]


def test_list_logs_returns_rows_as_stored(monkeypatch):
    stored = _stored_rows()

    async def fake_run_db(fn, *args, **kwargs):
        return stored

    monkeypatch.setattr(api, "run_db", fake_run_db)
    monkeypatch.setattr(api, "connect", lambda: FakeConn())

    async def main():
        client = api.app.test_client()
        resp = await client.get(
            "/api/logs",
            headers={"Authorization": f"Bearer {_token('observer', 'reader')}"},
        )
        assert resp.status_code == 200
        return await resp.get_json()

    data = asyncio.run(main())
    assert data == stored
    assert data[0]["verdict"] == "合格" and data[0]["status"] == "done"
    assert data[1]["verdict"] == "偏航超差" and data[1]["status"] == "done"


# ---------- 权限：观察员只读不可报送；技师提交先落 pending 整行 ----------

def test_observer_cannot_submit(monkeypatch):
    monkeypatch.setattr(api, "connect", lambda: FakeConn())

    async def main():
        client = api.app.test_client()
        resp = await client.post(
            "/api/logs",
            json={"turbine_code": "W09", "yaw_err_deg": 0.1},
            headers={"Authorization": f"Bearer {_token('observer', 'reader')}"},
        )
        return resp.status_code

    assert asyncio.run(main()) == 403


def test_technician_submit_inserts_pending_row(monkeypatch):
    row = {
        "id": 3, "turbine_code": "W09", "yaw_err_deg": 0.1,
        "status": "pending", "verdict": None, "reason": None,
        "created_by": "technician", "created_at": None, "processed_at": None,
    }
    conn = FakeConn(returning=row)
    monkeypatch.setattr(api, "connect", lambda: conn)

    async def main():
        client = api.app.test_client()
        resp = await client.post(
            "/api/logs",
            json={"turbine_code": "W09", "yaw_err_deg": 0.1},
            headers={"Authorization": f"Bearer {_token('technician', 'writer')}"},
        )
        assert resp.status_code == 201
        return await resp.get_json()

    data = asyncio.run(main())
    assert data["status"] == "pending" and data["verdict"] is None
    assert len(conn.inserts) == 1
    sql, params = conn.inserts[0]
    assert "'pending'" in sql and "NULL, NULL" in sql
    assert params[:2] == ("W09", 0.1)
    assert conn.committed


# ---------- 启动修复：历史脏结论按规则重算（幂等） ----------

def test_reconcile_repairs_dirty_done_rows():
    dirty = [
        {"id": 1, "yaw_err_deg": 0.4, "verdict": "偏航超差", "reason": "旁路强制偏航超差"},
        {"id": 2, "yaw_err_deg": 3.2, "verdict": "偏航超差", "reason": "偏航误差 3.2° 超过 ±1.5°"},
    ]
    conn = FakeConn(listed=dirty)
    api.reconcile_done_rows(conn)
    assert len(conn.updates) == 1  # 仅重写被污染的行
    _, params = conn.updates[0]
    assert params[0] == "合格" and "在 ±1.5° 以内" in params[1] and params[2] == 1


# ---------- 陷阱模块必须彻底移除 ----------

def test_trap_modules_removed():
    for name in (
        "h01_extra_trap",
        "h01_list_trap",
        "h01_surface_trap",
        "verdict_force_fail",
    ):
        assert importlib.util.find_spec(name) is None, name

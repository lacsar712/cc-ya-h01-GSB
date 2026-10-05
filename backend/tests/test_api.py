"""列表接口：必须原样返回库内 status/verdict/reason，不得二次改写。"""

import asyncio
from datetime import datetime, timezone

import pytest

import api
from tests.fakes import FakeConn


def _row(row_id, code, err, status, verdict=None, reason=None):
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    return {
        "id": row_id,
        "turbine_code": code,
        "yaw_err_deg": err,
        "status": status,
        "verdict": verdict,
        "reason": reason,
        "created_by": "technician",
        "created_at": now,
        "processed_at": now if status == "done" else None,
    }


def _run(coro):
    return asyncio.run(coro)


def test_list_returns_db_rows_verbatim(monkeypatch):
    rows = [
        _row(2, "W07", 3.2, "done", "偏航超差", "偏航误差 3.2° 超过 ±1.5°"),
        _row(1, "W01", 0.4, "done", "合格", "偏航误差 0.4° 在 ±1.5° 以内"),
    ]
    monkeypatch.setattr(api, "connect", lambda: FakeConn(rows=rows))

    async def scenario():
        client = api.app.test_client()
        login = await client.post(
            "/api/auth/login",
            json={"username": "technician", "password": "tech123456"},
        )
        assert login.status_code == 200
        token = (await login.get_json())["access_token"]

        res = await client.get(
            "/api/logs", headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        return await res.get_json()

    data = _run(scenario())

    by_id = {r["id"]: r for r in data}
    # 库里已记合格的行，列表必须是合格、done，不能被改红或退回待处理
    assert by_id[1]["verdict"] == "合格"
    assert by_id[1]["status"] == "done"
    assert by_id[1]["reason"] == "偏航误差 0.4° 在 ±1.5° 以内"
    # 超差行也必须忠实呈现
    assert by_id[2]["verdict"] == "偏航超差"
    assert by_id[2]["status"] == "done"


def test_list_pending_row_stays_pending(monkeypatch):
    rows = [_row(3, "W12", 0.4, "pending")]
    monkeypatch.setattr(api, "connect", lambda: FakeConn(rows=rows))

    async def scenario():
        client = api.app.test_client()
        login = await client.post(
            "/api/auth/login",
            json={"username": "observer", "password": "obs123456"},
        )
        token = (await login.get_json())["access_token"]
        res = await client.get(
            "/api/logs", headers={"Authorization": f"Bearer {token}"}
        )
        return await res.get_json()

    data = _run(scenario())
    assert data[0]["status"] == "pending"
    assert data[0]["verdict"] is None


def test_list_requires_login(monkeypatch):
    monkeypatch.setattr(api, "connect", lambda: FakeConn(rows=[]))

    async def scenario():
        client = api.app.test_client()
        return await client.get("/api/logs")

    res = _run(scenario())
    assert res.status_code == 401


def test_observer_cannot_submit(monkeypatch):
    monkeypatch.setattr(api, "connect", lambda: FakeConn(rows=[]))

    async def scenario():
        client = api.app.test_client()
        login = await client.post(
            "/api/auth/login",
            json={"username": "observer", "password": "obs123456"},
        )
        token = (await login.get_json())["access_token"]
        return await client.post(
            "/api/logs",
            json={"turbine_code": "W20", "yaw_err_deg": 0.2},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

    res = _run(scenario())
    assert res.status_code == 403

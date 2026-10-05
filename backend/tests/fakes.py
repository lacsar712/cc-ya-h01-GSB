"""内存版 psycopg 连接，只实现 worker/api 用到的语义：

- with conn.transaction() 进入时打快照，正常退出提交，异常回滚；
- UPDATE 先作用于活动状态，事务回滚后必须恢复到提交快照，
  用来验证「写库中断不留半行脏数据」。
"""

import psycopg


class FakeResult:
    def __init__(self, rows=(), row=None):
        self._rows = list(rows)
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return list(self._rows)


class _Transaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn._begin()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.conn.rollback()
        else:
            self.conn.commit()
        return False


class FakeConn:
    def __init__(self, rows=(), fail_update=False):
        self.committed = [dict(r) for r in rows]
        self._snapshot = None
        self.fail_update = fail_update
        self.update_count = 0

    # `with connect() as conn`
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def transaction(self):
        return _Transaction(self)

    def _begin(self):
        self._snapshot = [dict(r) for r in self.committed]

    def commit(self):
        self._snapshot = None

    def rollback(self):
        if self._snapshot is not None:
            self.committed = self._snapshot
            self._snapshot = None

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("CREATE TABLE"):
            return FakeResult()
        if s.startswith("SELECT COUNT(*)"):
            return FakeResult(row={"n": len(self.committed)})
        if s.startswith("SELECT id, turbine_code, yaw_err_deg FROM yaw_logs"):
            row = next(
                (dict(r) for r in self.committed if r["status"] == "pending"),
                None,
            )
            return FakeResult(row=row)
        if s.startswith("UPDATE yaw_logs"):
            self.update_count += 1
            verdict, reason, processed_at, row_id = params
            target = next(r for r in self.committed if r["id"] == row_id)
            # 先把变更写到活动状态，模拟「已 UPDATE 但尚未 COMMIT」
            target.update(
                status="done",
                verdict=verdict,
                reason=reason,
                processed_at=processed_at,
            )
            if self.fail_update:
                raise psycopg.Error("simulated write interruption")
            return FakeResult()
        if s.startswith("SELECT id, turbine_code, yaw_err_deg, status, verdict"):
            return FakeResult(rows=[dict(r) for r in self.committed])
        raise AssertionError(f"unexpected SQL: {s}")

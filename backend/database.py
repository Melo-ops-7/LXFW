"""SQLite 数据访问层：连接管理、首次启动自动建库 + 种子数据。"""
import sqlite3
from contextlib import contextmanager

import config


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    """事务上下文：正常提交，异常回滚。"""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


def init_db():
    """执行 init.sql 建表；空库时写入种子数据（需求 13.2 异常恢复）。"""
    with db() as conn:
        sql = (config.BASE_DIR / "init.sql").read_text(encoding="utf-8")
        conn.executescript(sql)
        count = conn.execute("SELECT COUNT(*) FROM sys_user").fetchone()[0]
        if count == 0:
            import seed
            seed.run(conn)
"""API tests for /jobs server-side filtering (status multi-select + name keyword)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Job


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = TestingSession()

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    def _override_auth():
        return {"username": "tester", "role": "bioops"}

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_auth
    try:
        yield db
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.fixture()
def client(db_session):
    # j1 损坏名+失败 / j2 损坏名+成功 / j3 正常名+失败 / j4 正常名+成功
    db_session.add_all(
        [
            Job(sample_name="损坏样例A", status="failed", created_by="bioops", fastq_snapshot="x"),
            Job(sample_name="损坏样例A", status="success", created_by="bioops", fastq_snapshot="x"),
            Job(sample_name="正常样例B", status="failed", created_by="bioops", fastq_snapshot="x"),
            Job(sample_name="正常样例B", status="success", created_by="bioops", fastq_snapshot="x"),
        ]
    )
    db_session.commit()
    return TestClient(app)


def test_no_filter_returns_all(client):
    res = client.get("/api/jobs")
    assert res.status_code == 200
    rows = res.json()
    assert [r["id"] for r in rows] == [4, 3, 2, 1]


def test_status_multiselect_failed_only(client):
    res = client.get("/api/jobs", params=[("status", "failed")])
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 2
    assert {r["id"] for r in rows} == {1, 3}
    assert all(r["status"] == "failed" for r in rows)


def test_multiple_statuses(client):
    res = client.get("/api/jobs", params=[("status", "pending"), ("status", "running")])
    assert res.status_code == 200
    assert res.json() == []


def test_keyword_only(client):
    res = client.get("/api/jobs", params={"q": "损坏"})
    assert res.status_code == 200
    assert {r["id"] for r in res.json()} == {1, 2}


def test_status_and_keyword_are_and(client):
    # 自测场景：只勾失败 + “损坏”关键字 → 只剩同时命中的失败单 j1
    res = client.get(
        "/api/jobs",
        params=[("status", "failed"), ("q", "损坏")],
    )
    assert res.status_code == 200
    rows = res.json()
    assert [r["id"] for r in rows] == [1]
    assert rows[0]["status"] == "failed"
    assert "损坏" in rows[0]["sample_name"]


def test_keyword_no_match_returns_empty_not_full(client):
    # 没命中必须是空表，服务端不得回退成全量
    res = client.get("/api/jobs", params={"q": "不存在的关键字"})
    assert res.status_code == 200
    assert res.json() == []


def test_invalid_status_rejected(client):
    res = client.get("/api/jobs", params=[("status", "bogus")])
    assert res.status_code == 422


def test_auditor_role_may_filter(client):
    # 两角色可用：auditor 同样能使用筛选接口
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "auditor",
        "role": "auditor",
    }
    res = client.get("/api/jobs", params=[("status", "failed"), ("q", "损坏")])
    assert res.status_code == 200
    assert [r["id"] for r in res.json()] == [1]

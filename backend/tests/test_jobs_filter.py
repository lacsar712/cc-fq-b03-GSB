"""作业历史服务端过滤测试（sqlite 内存库 + 依赖覆盖，不依赖 PostgreSQL）。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import router
from app.auth import create_access_token
from app.database import Base, get_db
from app.models import Job


def _headers(username: str, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(username, role)}"}


BIOOPS = _headers("bioops", "bioops")
AUDITOR = _headers("auditor", "auditor")


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    db = TestingSession()
    db.add_all(
        [
            Job(sample_name="demo-good-r1", status="success", created_by="bioops", fastq_snapshot="x"),
            Job(sample_name="demo-broken-malformed", status="failed", created_by="bioops", fastq_snapshot="x"),
            Job(sample_name="demo-broken-malformed", status="success", created_by="bioops", fastq_snapshot="x"),
            Job(sample_name="自定义输入", status="pending", created_by="bioops", fastq_snapshot="x"),
        ]
    )
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _names(resp) -> list[str]:
    return [j["sample_name"] for j in resp.json()]


def test_no_filters_returns_all(client):
    resp = client.get("/api/jobs", headers=BIOOPS)
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_filter_by_single_status(client):
    resp = client.get("/api/jobs", params={"status": "failed"}, headers=BIOOPS)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["sample_name"] == "demo-broken-malformed"


def test_filter_by_multiple_statuses(client):
    resp = client.get(
        "/api/jobs",
        params=[("status", "failed"), ("status", "pending")],
        headers=BIOOPS,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2
    assert {r["status"] for r in rows} == {"failed", "pending"}


def test_filter_by_keyword_case_insensitive(client):
    resp = client.get("/api/jobs", params={"keyword": "BROKEN"}, headers=BIOOPS)
    assert resp.status_code == 200
    assert _names(resp) == ["demo-broken-malformed", "demo-broken-malformed"]


def test_filter_status_and_keyword_stacked(client):
    """自测场景：只勾失败 + 损坏样例关键字 → 只剩匹配的失败单。"""
    resp = client.get(
        "/api/jobs",
        params=[("status", "failed"), ("keyword", "broken")],
        headers=BIOOPS,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["sample_name"] == "demo-broken-malformed"


def test_no_match_returns_empty_not_full_list(client):
    """无命中必须返回空表，禁止回退为全量。"""
    resp = client.get(
        "/api/jobs",
        params=[("status", "failed"), ("keyword", "good")],
        headers=BIOOPS,
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_keyword_only_no_match_returns_empty(client):
    resp = client.get("/api/jobs", params={"keyword": "不存在的样例"}, headers=BIOOPS)
    assert resp.status_code == 200
    assert resp.json() == []


def test_invalid_status_rejected(client):
    resp = client.get("/api/jobs", params={"status": "bogus"}, headers=BIOOPS)
    assert resp.status_code == 400
    assert "无效状态值" in resp.json()["detail"]


def test_auditor_can_filter_too(client):
    """两角色均可使用过滤。"""
    resp = client.get(
        "/api/jobs",
        params=[("status", "failed"), ("keyword", "broken")],
        headers=AUDITOR,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_unauthenticated_rejected(client):
    resp = client.get("/api/jobs", params={"status": "failed"})
    assert resp.status_code == 401

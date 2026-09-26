"""Knowledge assistant tests: ingestion, retrieval, grounding checks, the SMS
path and source safety rules. The LLM and the network are faked."""
import os

os.environ["SEED_DEMO_DATA"] = "false"
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_hackathon.db")

import asyncio  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.communications import service as comms_service_module  # noqa: E402
from app.modules.communications.sms import SMSProvider, SmsSendResult  # noqa: E402
from app.modules.knowledge import assistant as assistant_module  # noqa: E402
from app.modules.knowledge import ingest  # noqa: E402
from app.modules.knowledge.assistant import verify_answer  # noqa: E402

FAQ = """Mama Mboga Grocers — Frequently asked questions

Opening hours: We are open Monday to Saturday from 8am to 7pm. We are closed on Sundays.

Delivery: We deliver within Nairobi for KES 150. Orders above KES 2,000 get free delivery.

Payment: We accept M-Pesa (Till 552211), cash on delivery and Visa cards."""

OUTBOX: list[dict] = []
# What the fake model should answer next (set per test).
NEXT_ANSWER: dict = {}


class FakeSMS(SMSProvider):
    async def send_sms(self, to, text, sender_id=None):
        OUTBOX.append({"to": to, "text": text, "from": sender_id})
        return SmsSendResult(message_id=f"k-{len(OUTBOX)}", status="success", provider="fake")


async def fake_chat_json(system, user, **_):
    if "prepare a knowledge-base search" in system:
        greeting = user.strip().lower() in ("hi", "hello", "asante")
        return {"language": "en", "is_question": not greeting, "question_en": user,
                "keywords": ["open", "hours", "delivery", "payment", "mpesa"]}
    return dict(NEXT_ANSWER)


@pytest.fixture(scope="module")
def client():
    saved = {k: getattr(settings, k) for k in ("ai_api_key", "ai_provider", "allow_private_sources")}
    original_sms = comms_service_module.get_sms_provider
    original_chat = assistant_module.chat_json
    settings.ai_api_key, settings.ai_provider = "test-key", "deepseek"
    comms_service_module.get_sms_provider = lambda: FakeSMS()
    assistant_module.chat_json = fake_chat_json
    with TestClient(app) as c:
        c.put("/api/v1/knowledge/profile", json={
            "name": "Mama Mboga Grocers", "description": "Fresh groceries in Nairobi",
            "contact": "+254700111222", "fallback_message": "Sorry, I can't answer that yet.",
            "assistant_enabled": True,
        })
        resp = c.post("/api/v1/knowledge/sources", json={"kind": "text", "name": "FAQ", "config": {"text": FAQ}})
        assert resp.status_code == 202, resp.text
        yield c
    for key, value in saved.items():
        setattr(settings, key, value)
    comms_service_module.get_sms_provider = original_sms
    assistant_module.chat_json = original_chat


def _ask(client, question):
    resp = client.post("/api/v1/knowledge/ask", json={"question": question})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_text_source_is_imported(client):
    sources = client.get("/api/v1/knowledge/sources").json()
    faq = next(s for s in sources if s["name"] == "FAQ")
    assert faq["status"] == "ready" and faq["chunk_count"] >= 1
    chunks = client.get(f"/api/v1/knowledge/sources/{faq['id']}/chunks").json()
    assert "8am to 7pm" in " ".join(c["content"] for c in chunks)
    profile = client.get("/api/v1/knowledge/profile").json()
    assert profile["available"] is True and profile["ready_sources"] >= 1


def test_grounded_answer_is_sent(client):
    NEXT_ANSWER.clear()
    NEXT_ANSWER.update({"answerable": True, "answer": "We're open Monday to Saturday, 8am to 7pm.",
                        "evidence": ["open Monday to Saturday from 8am to 7pm"], "sources": ["S1"]})
    body = _ask(client, "When are you open?")
    assert body["answered"] is True and "8am" in body["answer"]
    assert body["sources"][0]["source_name"] == "FAQ"


def test_invented_quote_is_blocked(client):
    NEXT_ANSWER.clear()
    NEXT_ANSWER.update({"answerable": True, "answer": "Yes, we open on Sundays.",
                        "evidence": ["open every Sunday"], "sources": ["S1"]})
    body = _ask(client, "Are you open on Sunday?")
    assert body["answered"] is False and body["reason"] == "unverified"
    assert body["answer"].startswith("Sorry, I can't answer that yet.") and "+254700111222" in body["answer"]


def test_invented_number_is_blocked(client):
    NEXT_ANSWER.clear()
    NEXT_ANSWER.update({"answerable": True, "answer": "Delivery costs KES 300.",
                        "evidence": ["We deliver within Nairobi"], "sources": ["S1"]})
    assert _ask(client, "How much is delivery?")["reason"] == "unverified"


def test_model_declines_when_not_in_sources(client):
    NEXT_ANSWER.clear()
    NEXT_ANSWER.update({"answerable": False, "answer": "", "evidence": []})
    body = _ask(client, "Do you sell payment phones?")
    assert body["answered"] is False and body["reason"] == "not_in_sources"


def test_no_matching_passage(client):
    body = _ask(client, "zebra xylophone quantum")
    assert body["answered"] is False


def test_greeting_gets_welcome(client):
    body = _ask(client, "hello")
    assert body["reason"] == "not_a_question" and "Mama Mboga Grocers" in body["answer"]


def test_unanswered_questions_are_listed(client):
    queries = client.get("/api/v1/knowledge/queries", params={"unanswered": True}).json()
    assert any(q["question"] == "Are you open on Sunday?" for q in queries)


def test_sms_question_is_answered(client):
    # Make the relay the active SMS workflow.
    for wf in client.get("/api/v1/workflows").json():
        if wf["status"] == "active":
            client.patch(f"/api/v1/workflows/{wf['id']}", json={"status": "inactive"})
    wf = client.post("/api/v1/workflows", json={"name": "Relay for knowledge test", "definition": {
        "nodes": [{"id": "1", "type": "incoming_sms", "config": {}},
                  {"id": "2", "type": "bridge_relay", "config": {}}],
        "edges": [{"source": "1", "target": "2"}]}}).json()
    client.patch(f"/api/v1/workflows/{wf['id']}", json={"status": "active"})
    try:
        NEXT_ANSWER.clear()
        NEXT_ANSWER.update({"answerable": True, "answer": "We accept M-Pesa (Till 552211), cash on delivery and Visa.",
                            "evidence": ["We accept M-Pesa (Till 552211)"], "sources": ["S1"]})
        OUTBOX.clear()
        resp = client.post("/api/v1/webhooks/africastalking/sms", data={
            "from": "+254722000999", "to": "57000", "text": "How can I pay?", "id": "kq-1"})
        assert resp.status_code == 200
        assert OUTBOX and OUTBOX[0]["to"] == "+254722000999" and "552211" in OUTBOX[0]["text"]
        assert OUTBOX[0]["from"] == "57000"
        log = client.get("/api/v1/messages/log", params={"phone": "+254722000999"}).json()
        assert any(m["kind"] == "answer" for m in log)
    finally:
        client.patch(f"/api/v1/workflows/{wf['id']}", json={"status": "inactive"})


def test_knowledge_node_in_workflow(client):
    NEXT_ANSWER.clear()
    NEXT_ANSWER.update({"answerable": True, "answer": "Free delivery on orders above KES 2,000.",
                        "evidence": ["Orders above KES 2,000 get free delivery"], "sources": ["S1"]})
    wf = client.post("/api/v1/workflows", json={"name": "FAQ bot", "definition": {
        "nodes": [{"id": "1", "type": "incoming_sms", "config": {}},
                  {"id": "2", "type": "knowledge_answer", "config": {}},
                  {"id": "3", "type": "send_sms", "config": {"text": "{{answer}}"}}],
        "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]}}).json()
    OUTBOX.clear()
    run = client.post(f"/api/v1/workflows/{wf['id']}/test-run",
                      json={"payload": {"from": "+254733000111", "text": "Is delivery free?"}}).json()
    assert run["status"] == "completed", run
    assert run["variables"]["answered"] == "1" and "2,000" in run["variables"]["answer"]


# ---------------------------------------------------------------- units
def test_verify_answer_rules():
    context = "Delivery costs KES 1,500.00 within Nairobi. Call +254 700 111 222."
    assert verify_answer("Delivery is KES 1500", ["Delivery costs KES 1,500.00"], context)[0]
    assert verify_answer("Call 254700111222", ["Call +254 700 111 222"], context)[0]
    assert not verify_answer("Delivery is KES 900", ["Delivery costs KES 1,500.00"], context)[0]
    assert not verify_answer("Delivery is KES 1500", ["made up quote"], context)[0]


def test_query_validation():
    assert ingest.validate_query("SELECT name, price FROM products;") == "SELECT name, price FROM products"
    assert ingest.validate_query("with t as (select 1) select * from t").startswith("with")
    for bad in ("DELETE FROM products", "SELECT 1; DROP TABLE x", "update t set a=1",
                "select * from t where id in (delete from t returning id)"):
        with pytest.raises(ingest.IngestError):
            ingest.validate_query(bad)
    assert ingest.validate_query("select * from t where note = 'please delete me'")


def test_private_hosts_are_refused():
    async def check(host):
        with pytest.raises(ingest.IngestError):
            await ingest.assert_public_host(host)
    for host in ("127.0.0.1", "localhost", "10.0.0.5", "169.254.169.254", "192.168.1.10"):
        asyncio.run(check(host))


def test_website_crawl(monkeypatch):
    pages = {
        "https://shop.example/": '<html><head><title>Home</title><meta name="description" content="Fresh fruit shop"></head>'
                                 '<body><script>var x=1</script><p>Welcome to our shop.</p>'
                                 '<a href="/prices">Prices</a><a href="https://other.example/x">x</a>'
                                 '<a href="/logo.png">logo</a></body></html>',
        "https://shop.example/prices": "<html><head><title>Prices</title></head><body><ul><li>Mangoes: KES 50</li>"
                                       "<li>Bananas: KES 10</li></ul></body></html>",
    }

    def handler(request):
        url = str(request.url).rstrip("/")
        for known, html in pages.items():
            if known.rstrip("/") == url:
                return httpx.Response(200, html=html)
        return httpx.Response(404)

    async def allow(host):
        return None

    monkeypatch.setattr(ingest, "assert_public_host", allow)
    monkeypatch.setattr(ingest, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    chunks = asyncio.run(ingest.ingest_website("shop.example", max_pages=5))
    text = "\n".join(c.content for c in chunks)
    assert "Mangoes: KES 50" in text and "Fresh fruit shop" in text
    assert "var x" not in text
    assert {c.location.rstrip("/") for c in chunks} == {"https://shop.example", "https://shop.example/prices"}


def test_google_doc_requires_sharing(monkeypatch):
    doc = "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz012345/edit"

    def handler(request):
        assert "export?format=txt" in str(request.url)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html>Sign in</html>")

    async def allow(host):
        return None

    monkeypatch.setattr(ingest, "assert_public_host", allow)
    monkeypatch.setattr(ingest, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(ingest.IngestError, match="Anyone with the link"):
        asyncio.run(ingest.ingest_google_doc(doc))


def test_google_sheet_rows(monkeypatch):
    sheet = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz012345/edit#gid=77"

    def handler(request):
        assert "gid=77" in str(request.url)
        return httpx.Response(200, headers={"content-type": "text/csv"},
                              text="Product,Price\nMangoes,50\nBananas,10\n")

    async def allow(host):
        return None

    monkeypatch.setattr(ingest, "assert_public_host", allow)
    monkeypatch.setattr(ingest, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    chunks = asyncio.run(ingest.ingest_google_sheet(sheet))
    assert "Product: Mangoes; Price: 50" in chunks[0].content


def test_database_source_secret_is_write_only(client):
    resp = client.post("/api/v1/knowledge/sources", json={
        "kind": "database", "name": "Stock",
        "config": {"query": "select name, qty from stock"},
        "secret": "postgresql://user:hunter2@127.0.0.1:5432/shop",
    })
    assert resp.status_code == 202
    body = resp.json()
    assert "hunter2" not in resp.text and body["has_secret"] is True
    source = next(s for s in client.get("/api/v1/knowledge/sources").json() if s["id"] == body["id"])
    # Private address is refused at sync time; the error never echoes the DSN.
    assert source["status"] == "error" and "private" in source["error"]
    assert "hunter2" not in source["error"]
    assert client.post("/api/v1/knowledge/sources", json={
        "kind": "database", "config": {"query": "drop table stock"}, "secret": "postgresql://h/db"}).status_code == 422
    client.delete(f"/api/v1/knowledge/sources/{body['id']}")

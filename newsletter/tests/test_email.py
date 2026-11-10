import email
from email import policy

import yaml

from newsletter import send_email
from newsletter.send_email import attachment_name, build_message


def test_message_structure(edition, cfg):
    msg = build_message(edition, cfg, draft=False, pr_url=None,
                        sender="from@example.invalid", recipients="to@example.invalid")
    assert msg["Subject"] == "IncreaseNET AI Community – Newsletter #3 (28 Oct – 10 Nov 2026)"
    assert msg.get_content_type() == "multipart/mixed"
    alt = msg.get_payload()[0]
    assert alt.get_content_type() == "multipart/alternative"
    assert [p.get_content_type() for p in alt.get_payload()] == ["text/plain", "text/html"]
    att = [p for p in msg.iter_attachments()]
    assert len(att) == 1 and att[0].get_filename() == attachment_name(edition) == "IncreaseNET-AI-Newsletter-2026-11-10.html"
    html = alt.get_payload()[1].get_content()
    assert "View this edition online" in html
    # no embedded images: only text parts + the HTML attachment
    assert not any(p.get_content_maintype() == "image" for p in msg.walk())


def test_draft_subject_prefix(edition, cfg):
    msg = build_message(edition, cfg, draft=True, pr_url="https://github.com/o/r/pull/1",
                        sender="a@b.invalid", recipients="c@d.invalid")
    assert msg["Subject"].startswith("[DRAFT] IncreaseNET AI Community – Newsletter #3")
    assert "https://github.com/o/r/pull/1" in msg.get_payload()[0].get_payload()[0].get_content()


def test_dry_run_writes_eml_without_credentials(edition, cfg, tmp_path, monkeypatch):
    for k in send_email.REQUIRED:
        monkeypatch.delenv(k, raising=False)
    draft = tmp_path / "2026-11-10.yaml"
    draft.write_text(yaml.safe_dump(edition, allow_unicode=True), encoding="utf-8")
    out = tmp_path / "test.eml"
    assert send_email.main(["--draft", str(draft), "--dry-run", "--out", str(out)]) == 0
    parsed = email.message_from_bytes(out.read_bytes(), policy=policy.default)
    assert parsed["Subject"].startswith("[DRAFT]")


def test_real_send_requires_env(edition, tmp_path, monkeypatch):
    for k in send_email.REQUIRED:
        monkeypatch.delenv(k, raising=False)
    draft = tmp_path / "d.yaml"
    draft.write_text(yaml.safe_dump(edition, allow_unicode=True), encoding="utf-8")
    assert send_email.main(["--draft", str(draft)]) == 3

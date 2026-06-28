from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
import uuid

BASE = os.getenv("LESSON_BASE_URL", "http://localhost:8000")
_FINAL_VIEWS = {"day_done", "day_blocked", "course_complete"}


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


class Session:
    def __init__(self) -> None:
        self.cookie: str | None = None

    def call(self, method: str, path: str, body=None, *, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode()
            payload = json.loads(body_text) if body_text else {}
            print(f"  -> HTTP {exc.code}: {body_text}")
            return exc.code, payload
        if resp.headers.get("Set-Cookie"):
            self.cookie = resp.headers.get("Set-Cookie").split(";")[0]
        text = resp.read().decode()
        return resp.status, json.loads(text)


def register(sess: Session, name: str, idem_key: str) -> dict:
    status, payload = sess.call(
        "POST",
        "/api/registration",
        {
            "name": name,
            "grade": 9,
            "ogeprep_answer": None,
            "pd_consent_checked": True,
            "policy_version_shown": "2026-06-19",
        },
        headers={"Idempotency-Key": idem_key},
    )
    expect(status in (200, 201), f"registration failed: HTTP {status} {payload}")
    return payload


def step(label: str, status: int, render: dict) -> dict:
    print(f"[{label}] HTTP {status} -> {json.dumps(render, ensure_ascii=False)}")
    return render


def advance_through_nonquestion(sess: Session, label_prefix: str) -> dict:
    """Жмёт advance, пока не дойдёт до question-view или финального экрана."""
    for _ in range(20):
        status, render = sess.call("GET", "/api/lesson/current")
        expect(status == 200, f"{label_prefix}: GET current failed with HTTP {status}")
        msg = render.get("message")
        if msg and msg.get("options"):
            return render
        seq = render.get("seq", 0)
        status, render = sess.call("POST", "/api/lesson/advance", {"seq": seq})
        step(f"{label_prefix}/advance", status, render)
        expect(status == 200, f"{label_prefix}: advance failed with HTTP {status}")
        msg = render.get("message")
        if msg and msg.get("options"):
            return render
        if render.get("view") in _FINAL_VIEWS:
            return render
    raise SystemExit(f"{label_prefix}: too many non-question advance steps")


def answer(sess: Session, label: str, letter: str) -> dict:
    status, render = sess.call("GET", "/api/lesson/current")
    expect(status == 200, f"{label}: GET current failed with HTTP {status}")
    msg = render["message"]
    status, render = sess.call(
        "POST",
        "/api/lesson/answer",
        {"message_id": msg["message_id"], "selected": letter, "seq": render["seq"]},
    )
    step(label, status, render)
    expect(status == 200, f"{label}: answer failed with HTTP {status}")
    return render


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-проверка lesson-flow через живой backend API."
    )
    parser.add_argument("scenario", choices=("mastery", "fail", "cancel"))
    parser.add_argument(
        "idempotency_key",
        nargs="?",
        default=str(uuid.uuid4()),
        help="UUID для Idempotency-Key; по умолчанию генерируется автоматически.",
    )
    return parser.parse_args()


def run_mastery(sess: Session) -> None:
    for letter in ["A", "B", "D"]:
        advance_through_nonquestion(sess, "mastery")
        answer(sess, "mastery/training-answer", letter)
    answer(sess, "mastery/main_question-WRONG", "B")
    advance_through_nonquestion(sess, "mastery/after-wrong")
    final = answer(sess, "mastery/backup-CORRECT", "B")
    expect(final.get("fsm_state") == "lesson_final", "mastery: expected lesson_final")


def run_fail(sess: Session) -> None:
    advance_through_nonquestion(sess, "fail")
    for letter in ["B", "C", "D"]:
        answer(sess, f"fail/training-wrong-{letter}", letter)
    status, current = sess.call("GET", "/api/lesson/current")
    step("fail/current", status, current)
    expect(current.get("fsm_state") == "lesson_failed", "fail: expected lesson_failed")
    seq = current.get("seq", 0)
    status, blocked = sess.call("POST", "/api/lesson/advance", {"seq": seq})
    step("fail/advance-to-blocked", status, blocked)
    expect(blocked.get("view") == "day_blocked", "fail: expected day_blocked")
    status, day = sess.call("GET", "/api/day")
    step("fail/day-after-blocked", status, day)
    expect(
        day.get("day", {}).get("has_lesson_today") is False,
        "fail: day should be blocked",
    )


def run_cancel(sess: Session) -> None:
    advance_through_nonquestion(sess, "cancel")
    status, before = sess.call("GET", "/api/lesson/current")
    step("cancel/before", status, before)
    expect(
        before.get("fsm_state") == "lesson_training",
        "cancel: expected lesson_training before cancel",
    )
    seq = before.get("seq", 0)
    status, render = sess.call("POST", "/api/lesson/cancel", {"seq": seq})
    step("cancel/cancel", status, render)
    expect(
        render.get("fsm_state") == "registered",
        "cancel: expected registered after cancel",
    )
    status, day = sess.call("GET", "/api/day")
    step("cancel/day-after-cancel", status, day)
    status, opened = sess.call("POST", "/api/day/open")
    step("cancel/day-open-again", status, opened)
    status, e7 = sess.call("GET", "/api/lesson/current")
    step("cancel/resume-E7", status, e7)
    expect(
        e7.get("message", {}).get("message_id")
        == before.get("message", {}).get("message_id"),
        "cancel: E7 resume lost saved message",
    )
    status, resumed = sess.call("POST", "/api/day/warmup", {"action": "skip", "seq": 0})
    step("cancel/warmup-skip-again", status, resumed)
    same = resumed.get("message", {}).get("message_id") == before.get(
        "message", {}
    ).get("message_id") and resumed.get("fsm_state") == before.get("fsm_state")
    print("RESUME MATCHES PRE-CANCEL POINT:", same)
    expect(same, "cancel: resume via start path did not match pre-cancel point")


def main() -> None:
    args = parse_args()
    print(f"BASE={BASE}")
    print(f"SCENARIO={args.scenario}")
    print(f"IDEMPOTENCY_KEY={args.idempotency_key}")

    sess = Session()
    reg = register(sess, f"Smoke {args.scenario}", args.idempotency_key)
    print("registered:", reg)

    status, day_open = sess.call("POST", "/api/day/open")
    step("day-open", status, day_open)
    expect(status == 200, "day-open failed")

    status, warmup = sess.call("POST", "/api/day/warmup", {"action": "skip", "seq": 0})
    step("warmup-skip", status, warmup)
    expect(status == 200, "warmup-skip failed")
    expect(
        warmup.get("fsm_state", "").startswith("lesson_"),
        "warmup-skip should enter lesson flow",
    )

    if args.scenario == "mastery":
        run_mastery(sess)
    elif args.scenario == "fail":
        run_fail(sess)
    else:
        run_cancel(sess)

    print("SCENARIO PASSED")


if __name__ == "__main__":
    main()

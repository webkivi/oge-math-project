import json
import sys
import urllib.request

BASE = "http://localhost:8000"


class Session:
    def __init__(self):
        self.cookie = None

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            print(f"  -> HTTP {e.code}: {body_text}")
            return e.code, json.loads(body_text) if body_text else {}
        if resp.headers.get("Set-Cookie"):
            self.cookie = resp.headers.get("Set-Cookie").split(";")[0]
        text = resp.read().decode()
        return resp.status, json.loads(text)


def register(sess, name, idem_key):
    body = {
        "name": name,
        "grade": 9,
        "ogeprep_answer": None,
        "pd_consent_checked": True,
        "policy_version_shown": "2026-06-19",
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + "/api/registration", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Idempotency-Key", idem_key)
    resp = urllib.request.urlopen(req)
    if resp.headers.get("Set-Cookie"):
        sess.cookie = resp.headers.get("Set-Cookie").split(";")[0]
    return json.loads(resp.read().decode())


def step(label, status, render):
    print(f"[{label}] HTTP {status} -> {json.dumps(render, ensure_ascii=False)}")
    return render


def advance_through_nonquestion(sess, label_prefix):
    """Жмёт advance, пока не дойдёт до стадии с options (вопрос)."""
    while True:
        status, render = sess.call("GET", "/api/lesson/current")
        msg = render.get("message")
        if msg and msg.get("options"):
            return render
        seq = render.get("seq", 0)
        status, render = sess.call("POST", "/api/lesson/advance", {"seq": seq})
        step(f"{label_prefix}/advance", status, render)
        msg = render.get("message")
        if msg and msg.get("options"):
            return render
        if render.get("view") in ("day_done", "day_blocked", "course_complete"):
            return render


def answer(sess, label, letter):
    status, render = sess.call("GET", "/api/lesson/current")
    msg = render["message"]
    status, render = sess.call(
        "POST",
        "/api/lesson/answer",
        {"message_id": msg["message_id"], "selected": letter, "seq": render["seq"]},
    )
    step(label, status, render)
    return render


def main():
    scenario = sys.argv[1]
    sess = Session()
    idem = sys.argv[2]
    reg = register(sess, f"Test {scenario}", idem)
    print("registered:", reg)
    sess.call("POST", "/api/day/open")
    status, r = sess.call("POST", "/api/day/warmup", {"action": "skip", "seq": 0})
    step("warmup-skip", status, r)
    status, r = sess.call("POST", "/api/lesson/start", {"seq": 0})
    step("lesson-start", status, r)

    if scenario == "mastery":
        # Дойти до первого training-вопроса и ответить верно на все 3
        for letter in ["A", "B", "D"]:
            r = advance_through_nonquestion(sess, "mastery")
            r = answer(sess, "mastery/training-answer", letter)
        # main_question (Q4, correct=A) — ответим WRONG (B) -> attempt1 wrong
        r = answer(sess, "mastery/main_question-WRONG", "B")
        # theory_review -> advance -> main_question_backup
        r = advance_through_nonquestion(sess, "mastery/after-wrong")
        # Q4b correct=B -> attempt2 correct
        r = answer(sess, "mastery/backup-CORRECT", "B")

    elif scenario == "fail":
        r = advance_through_nonquestion(sess, "fail")
        # Q1 correct=A; ответим неверно 3 раза подряд (B, C, D)
        for letter in ["B", "C", "D"]:
            r = answer(sess, f"fail/training-wrong-{letter}", letter)
        # должно быть lesson_failed -> advance -> daily_blocked
        status, r = sess.call("GET", "/api/lesson/current")
        step("fail/current", status, r)
        seq = r.get("seq", 0)
        status, r = sess.call("POST", "/api/lesson/advance", {"seq": seq})
        step("fail/advance-to-blocked", status, r)
        status, r = sess.call("GET", "/api/day")
        step("fail/day-after-blocked", status, r)

    elif scenario == "cancel":
        r = advance_through_nonquestion(sess, "cancel")
        status, r = sess.call("GET", "/api/lesson/current")
        before = r
        step("cancel/before", status, r)
        seq = r.get("seq", 0)
        status, r = sess.call("POST", "/api/lesson/cancel", {"seq": seq})
        step("cancel/cancel", status, r)
        status, r = sess.call("GET", "/api/day")
        step("cancel/day-after-cancel", status, r)
        # снова открыть день и резюмировать урок
        status, r = sess.call("POST", "/api/day/open")
        step("cancel/day-open-again", status, r)
        status, r = sess.call("GET", "/api/lesson/current")
        step("cancel/resume-E7", status, r)
        status, r = sess.call("POST", "/api/day/warmup", {"action": "skip", "seq": 0})
        step("cancel/warmup-skip-again", status, r)
        status, r = sess.call("POST", "/api/lesson/start", {"seq": 0})
        step("cancel/resume-via-start", status, r)
        same = (
            r.get("message", {}).get("message_id") == before.get("message", {}).get("message_id")
            and r.get("fsm_state") == before.get("fsm_state")
        )
        print("RESUME MATCHES PRE-CANCEL POINT:", same)


if __name__ == "__main__":
    main()

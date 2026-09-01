"""매달 1일 학부모에게 월간 마스터플랜을 자동 발송한다 (GitHub Actions 용).

명단은 로컬 PC 가 SRDB 에서 뽑아 구글 시트에 올려둔다 (SRDB-Browser 의
newsletter_roster.py). SRDB 는 Cloudflare Turnstile 때문에 실제 브라우저 창이
필요해 클라우드에서 못 긁는다 — 그래서 "명단 만들기"와 "발송"을 나눴다.

시트의 roster 탭:  email | grades | name | children | source
  grades 가 "9,11" 이면 그 학년 섹션만, 비어 있으면 9~12학년 전체를 보낸다.
  children 은 "Ashley:9;Kaylin:10" — 학년 섹션 제목에 자녀 이름을 붙일 때 쓴다.

시트의 optout 탭:  수신을 원치 않는 주소. 발송 직전에 받은편지함을 훑어
  "Unsubscribe"/"수신거부" 회신을 찾아 여기에 자동으로 추가하고 제외한다.
  잘못 빠진 사람이 있으면 이 탭에서 그 줄을 지우면 다시 받는다.

필요한 환경변수:
  GOOGLE_API_KEY               Gemini
  SENDER_EMAIL / SENDER_PASSWORD   Gmail SMTP (앱 비밀번호)
  GOOGLE_SERVICE_ACCOUNT_JSON  서비스 계정 키 JSON 통째로
  ROSTER_SHEET_KEY             명단 시트 키
  TEST_RECIPIENT               --test 로 보낼 주소 (없으면 SENDER_EMAIL)

사용법:
  python newsletter_send.py --test      # 원장님 주소로만 (본문은 실제와 동일)
  python newsletter_send.py --dry-run   # 생성만 하고 발송하지 않음
  python newsletter_send.py             # 전체 발송
"""
import json
import os
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import newsletter_utils

# 로컬에서 테스트할 때만 쓰인다. Actions 에서는 .env 가 없고 Secrets 가 환경변수로 들어온다.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

ROSTER_TAB = "roster"
OPTOUT_TAB = "optout"
ALL_GRADES = [9, 10, 11, 12]
SPLIT = "---KOREAN---"

# 앞의 모델이 은퇴하면 뒤로 넘어간다 — 무인 실행이라 한 번 죽으면 그 달을 통째로 놓친다
MODELS = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-flash-latest"]

ORDINAL = {9: "9th", 10: "10th", 11: "11th", 12: "12th"}

FOOTER = """

---

Sent by Elite Prep Master Plan & Academic Consulting

Andy Lee  | Branch Director <br>
Elite Prep Suwanee powered by Elite Open School <br>
1291 Old Peachtree Rd. NW #127, Suwanee, GA 30024 <br>
Tel & Text: 470.253.1004

<br>

*To stop receiving this monthly plan, simply reply to this email with "Unsubscribe".* <br>
*이 월간 안내를 받지 않으시려면 이 메일에 "수신거부"라고 회신해 주세요.*
"""


def env(name, default=None, required=False):
    v = os.getenv(name) or default
    if required and not v:
        raise SystemExit(f"[중단] 환경변수 {name} 이 필요합니다.")
    return v


# ---------------------------------------------------------------- 명단 읽기

def open_sheet():
    """명단 시트를 연다. optout 탭에 써야 하므로 읽기 전용이 아니다."""
    import gspread
    from google.oauth2.service_account import Credentials

    raw = env("GOOGLE_SERVICE_ACCOUNT_JSON", required=True)
    key = env("ROSTER_SHEET_KEY", required=True)

    creds = Credentials.from_service_account_info(
        json.loads(raw),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds).open_by_key(key)


def load_roster(sh):
    """구글 시트 roster 탭 → [(email, [학년...], name, {학년: [자녀이름]})]"""
    rows = sh.worksheet(ROSTER_TAB).get_all_values()

    out = []
    for r in rows[1:]:
        if not r or "@" not in (r[0] or ""):
            continue
        grades = [int(g) for g in (r[1] if len(r) > 1 else "").split(",")
                  if g.strip().isdigit()]
        out.append((r[0].strip(), sorted(set(grades) & set(ALL_GRADES)),
                    (r[2] if len(r) > 2 else "").strip(),
                    parse_children(r[3] if len(r) > 3 else "")))
    return out


def parse_children(raw):
    """"Ashley:9;Kaylin:10" → {9: ["Ashley"], 10: ["Kaylin"]}"""
    kids = {}
    for piece in str(raw or "").split(";"):
        name, _, grade = piece.partition(":")
        name, grade = name.strip(), grade.strip()
        if name and grade.isdigit():
            kids.setdefault(int(grade), []).append(name)
    return kids


# ------------------------------------------------------------- 수신거부 처리

# 회신 본문에서 이 중 하나라도 보이면 수신거부로 본다.
OPTOUT_WORDS = ("unsubscribe", "opt out", "opt-out", "remove me", "take me off",
                "수신거부", "수신 거부", "구독취소", "구독 취소", "발송중단",
                "그만 보내", "안 받고", "안받고")

# 인용문이 시작되는 지점. 여기부터는 우리가 보낸 원문이라 무시해야 한다 —
# 푸터에 'reply with "Unsubscribe"' 가 있어서, 안 자르면 모든 회신이 수신거부가 된다.
QUOTE_MARKERS = ("Sent by Elite Prep Master Plan", "-----Original Message-----",
                 "________________________________", "wrote:", "작성:")


def strip_quoted(text):
    """회신에서 사람이 새로 쓴 부분만 남긴다."""
    lines = []
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith(">"):
            break
        if any(m in line for m in QUOTE_MARKERS):
            break
        lines.append(line)
    return "\n".join(lines)


def message_text(msg):
    """메일에서 사람이 읽는 본문(text/plain 우선)을 뽑는다."""
    parts = []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_type() != "text/plain":
            continue
        if "attachment" in str(part.get("Content-Disposition") or ""):
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            parts.append(payload.decode(part.get_content_charset() or "utf-8",
                                        errors="replace"))
        except Exception:
            pass
    return "\n".join(parts)


def find_unsubscribes(sender, password):
    """받은편지함에서 뉴스레터 회신을 훑어 수신거부 요청을 찾는다.

    → [(이메일, 회신에서 사람이 쓴 첫 줄)]
    실패해도 절대 발송을 막지 않는다 — 수신거부를 못 읽는 것보다
    그달 발송이 통째로 죽는 쪽이 훨씬 나쁘다.
    """
    import email as emaillib
    import imaplib
    from email.utils import parseaddr

    found = []
    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com")
        M.login(sender, password)
        M.select("INBOX")
        # 우리 뉴스레터에 대한 회신만 본다. 아무 메일이나 훑으면 오탐이 난다.
        typ, data = M.search(None, '(SUBJECT "Monthly Academic Master Plan")')
        ids = data[0].split() if typ == "OK" and data and data[0] else []
        print(f"   뉴스레터 관련 메일 {len(ids)}통 확인 중…", flush=True)

        for num in ids:
            try:
                typ, raw = M.fetch(num, "(RFC822)")
                if typ != "OK" or not raw or not raw[0]:
                    continue
                msg = emaillib.message_from_bytes(raw[0][1])
                frm = parseaddr(msg.get("From") or "")[1].lower().strip()
                if not frm or frm == sender.lower():
                    continue
                reply = strip_quoted(message_text(msg))
                low = reply.lower()
                if any(w in low for w in OPTOUT_WORDS):
                    snippet = " ".join(reply.split())[:120]
                    found.append((frm, snippet))
            except Exception as e:
                print(f"   ! 메일 한 통 읽기 실패: {e}", flush=True)

        M.close()
        M.logout()
    except Exception as e:
        print(f"   ⚠️ 받은편지함을 읽지 못했습니다 (발송은 계속합니다): {e}", flush=True)

    # 같은 사람이 여러 번 회신했을 수 있다
    dedup = {}
    for addr, snippet in found:
        dedup.setdefault(addr, snippet)
    return sorted(dedup.items())


def read_optout(sh):
    """optout 탭의 주소 집합."""
    try:
        rows = sh.worksheet(OPTOUT_TAB).get_all_values()
    except Exception:
        return set()
    out = {r[0].strip().lower() for r in rows[1:] if r and "@" in (r[0] or "")}
    return out


def sync_optout(sh, sender, password, dry):
    """수신거부 회신을 찾아 optout 탭에 적고, 최종 제외 명단을 돌려준다."""
    current = read_optout(sh)
    requests = find_unsubscribes(sender, password)
    new = [(a, s) for a, s in requests if a not in current]

    if not new:
        print(f"   새 수신거부 없음 (기존 제외 {len(current)}명)", flush=True)
        return current

    print(f"   새 수신거부 {len(new)}명:", flush=True)
    for addr, snippet in new:
        print(f"     - {addr}  \"{snippet}\"", flush=True)

    if dry:
        print("   (--dry-run 이라 시트에 쓰지 않습니다)", flush=True)
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            sh.worksheet(OPTOUT_TAB).append_rows(
                [[a, today, f"자동: 회신 \"{s}\""] for a, s in new],
                value_input_option="RAW")
        except Exception as e:
            print(f"   ⚠️ optout 탭 기록 실패 (이번 발송에서는 제외됩니다): {e}",
                  flush=True)

    return current | {a for a, _s in new}


# ------------------------------------------------------------- 내용 생성

def prompt_for(grade, month, year):
    return f"""
You are an expert US college admissions consultant at Elite Prep.
You are writing to the PARENTS of {ORDINAL[grade]} grade students — not to the students.
Month: {month} {year}.

Write this month's action plan for these parents. Produce it TWICE:
first in English, then the same content in natural Korean for Korean-speaking parents.
Separate the two versions with a line containing exactly: {SPLIT}

Each version must follow this structure:
1. A one-sentence opening addressed to parents that says where their child stands in
   the academic year (e.g. a pivotal milestone, the halfway mark).
2. A line starting with "Target Focus:" (Korean version: "이달의 핵심:") — one clear headline.
3. A checklist of 3-4 specific, actionable items the student should complete this month.
   MUST use this exact format: "- [ ] Item text..."
4. A short paragraph headed "### Consultant's Tip" (Korean: "### 컨설턴트 조언")
   with one piece of bold advice, written so a parent knows how to support their child.

Rules:
- Do NOT include a title or heading with the grade or month — that is added separately.
- Do NOT use strikethrough (~~text~~). Use **bold** for emphasis.
- Keep each version under 200 words.
- The Korean version must read like it was written by a Korean consultant,
  not like a translation. Use 존댓말 addressed to 학부모님.
- Output Markdown only.
"""


def generate(api_key, grade, month, year):
    """한 학년 분량을 만들어 (영문, 국문) 으로 돌려준다."""
    import google.generativeai as genai
    genai.configure(api_key=api_key)

    last_err = None
    for name in MODELS:
        try:
            resp = genai.GenerativeModel(name).generate_content(
                prompt_for(grade, month, year))
            text = (resp.text or "").strip()
            if not text:
                raise RuntimeError("빈 응답")
            if SPLIT in text:
                en, ko = text.split(SPLIT, 1)
            else:
                # 구분선을 안 넣었으면 영문만 있는 것으로 본다
                en, ko = text, ""
            print(f"   > {ORDINAL[grade]} 생성 완료 (모델: {name})", flush=True)
            return en.strip(), ko.strip()
        except Exception as e:
            last_err = e
            print(f"   ! {name} 실패: {e}", flush=True)
    raise SystemExit(f"[중단] {ORDINAL[grade]} 내용 생성 실패: {last_err}")


# ------------------------------------------------------------- 메일 조립

def subject_for(grades, month, year):
    if len(grades) == len(ALL_GRADES):
        en, ko = "Grades 9-12", "9~12학년"
    else:
        en = " & ".join(ORDINAL[g] for g in grades)
        ko = "·".join(str(g) for g in grades) + "학년"
    return f"[{month} {year}] Monthly Academic Master Plan — {en} | {ko} 월간 마스터플랜"


def who(kids, grade):
    """그 학년에 해당하는 자녀 이름. 없으면 빈 문자열."""
    names = (kids or {}).get(grade) or []
    return " & ".join(names)


def body_for(grades, content, month, year, kids=None):
    parts = [f"# Elite Prep – {month} {year} Monthly Academic Master Plan\n"]
    for g in grades:
        tag = who(kids, g)
        head = f"{ORDINAL[g]} Grade" + (f" — {tag}" if tag else "")
        parts.append(f"## 📌 {head}\n{content[g][0]}\n")

    korean = []
    for g in grades:
        if not content[g][1]:
            continue
        tag = who(kids, g)
        head = f"{g}학년" + (f" — {tag}" if tag else "")
        korean.append(f"### 📌 {head}\n{content[g][1]}\n")
    if korean:
        parts.append("---\n\n## 한국어 안내\n")
        parts.extend(korean)

    parts.append(FOOTER)
    return "\n".join(parts)


# ------------------------------------------------------------------ 실행

def main():
    args = sys.argv[1:]
    test = "--test" in args
    dry = "--dry-run" in args

    now = datetime.now()
    month, year = now.strftime("%B"), now.year
    print(f"--- 📧 월간 마스터플랜 발송 · {now:%Y-%m-%d %H:%M} "
          f"({'테스트' if test else '드라이런' if dry else '실발송'}) ---", flush=True)

    api_key = env("GOOGLE_API_KEY", required=True)
    sender = env("SENDER_EMAIL", required=True)
    password = env("SENDER_PASSWORD", required=not dry)

    sh = open_sheet()

    # 발송 전에 처리한다 — 수신거부한 분께 한 통 더 보내고 나서 빼면 의미가 없다.
    print("[1/5] 수신거부 회신 확인 중…", flush=True)
    optout = sync_optout(sh, sender, password, dry) if password else set()

    print("[2/5] 명단 읽는 중…", flush=True)
    roster = [r for r in load_roster(sh) if r[0].lower() not in optout]
    if not roster:
        raise SystemExit("[중단] 명단이 비어 있습니다.")
    n_matched = sum(1 for _e, g, _n, _k in roster if g)
    print(f"   {len(roster)}명 (학년 맞춤 {n_matched} · 통합본 {len(roster) - n_matched})",
          flush=True)

    print(f"[3/5] {month} 내용 생성 중… (학년 4개)", flush=True)
    content = {}
    for i, g in enumerate(ALL_GRADES, 1):
        print(f"   [{i}/4] {ORDINAL[g]} Grade…", flush=True)
        content[g] = generate(api_key, g, month, year)
        if i < len(ALL_GRADES):
            time.sleep(2)          # 레이트리밋 여유

    print("[4/5] 메일 조립 중…", flush=True)
    outbox = []
    for email, grades, _name, kids in roster:
        gs = grades or ALL_GRADES
        outbox.append((email, subject_for(gs, month, year),
                       body_for(gs, content, month, year, kids)))

    if test:
        target = env("TEST_RECIPIENT", sender)
        # 학년 조합이 8가지라 다 보내면 받은편지함이 지저분해진다.
        # 통합본(9~12) · 단일학년 · 다자녀 조합 각 한 통이면 형식 확인에 충분하다.
        picked, seen = [], set()
        for _email, grades, _n, kids in roster:
            gs = grades or ALL_GRADES
            kind = ("all" if len(gs) == len(ALL_GRADES)
                    else "single" if len(gs) == 1 else "multi")
            if kind in seen:
                continue
            seen.add(kind)
            picked.append((target, f"[TEST] {subject_for(gs, month, year)}",
                           body_for(gs, content, month, year, kids)))
        outbox = picked
        print(f"   테스트 모드 — {target} 로 {len(outbox)}통 "
              f"(통합본·단일학년·다자녀 견본)", flush=True)

    if dry:
        print("\n--dry-run — 발송하지 않았습니다. 첫 통 미리보기:\n", flush=True)
        print(outbox[0][1], flush=True)
        print("-" * 60, flush=True)
        print(outbox[0][2][:1500], flush=True)
        return

    print(f"[5/5] 발송 중… ({len(outbox)}통)", flush=True)
    import smtplib
    img = newsletter_utils.load_logo_bytes()
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender, password)

    sent, failed = 0, []
    try:
        for i, (email, subj, body) in enumerate(outbox, 1):
            try:
                msg = newsletter_utils.build_message(sender, email, subj, body, img)
                server.sendmail(sender, email, msg.as_string())
                sent += 1
            except Exception as e:
                print(f"   ❌ {email}: {e}", flush=True)
                failed.append(email)
            if i % 10 == 0 or i == len(outbox):
                bar = "█" * (20 * i // len(outbox))
                print(f"   [{bar:<20}] {i}/{len(outbox)}", flush=True)
            time.sleep(0.3)
    finally:
        try:
            server.quit()
        except Exception:
            pass

    print(f"\n✅ {sent}통 발송 완료" + (f" · 실패 {len(failed)}: {failed}" if failed else ""),
          flush=True)

    # 발송 기록을 남긴다. Actions 가 이 파일을 커밋해서 레포 활동을 만들어 준다 —
    # 공개 레포는 60일간 활동이 없으면 GitHub 이 예약 실행을 꺼버리기 때문이다.
    log_path = os.getenv("SENT_LOG")
    if log_path:
        line = (f"- {now:%Y-%m-%d} · {month} {year} · {sent}통 발송"
                + (f" · 실패 {len(failed)}" if failed else "")
                + (" (테스트)" if test else "") + "\n")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
        print(f"기록: {log_path} ← {line.strip()}", flush=True)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

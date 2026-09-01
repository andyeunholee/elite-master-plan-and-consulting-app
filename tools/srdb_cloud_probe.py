"""실험: GitHub 서버에서도 SRDB 에 로그인할 수 있는가?

배경 — SRDB(app.eliteprep.com)는 Cloudflare Turnstile 로 헤드리스 브라우저를 막는다.
그래서 지금은 명단 갱신을 원장님 랩탑에서만 돌린다. 만약 클라우드에서도 로그인이
되면 랩탑이 완전히 필요 없어진다.

Turnstile 이 막는 게 "헤드리스"뿐이라면, 가상 화면(xvfb) 위에 진짜 창을 띄운
크롬은 통과할 수도 있다. 다만 데이터센터 IP 는 Turnstile 이 더 깐깐하게 보므로
실패할 가능성이 더 크다고 본다 — 그래서 '실험'이다.

이 스크립트는 명단을 건드리지 않는다. 로그인해서 토큰이 나오는지만 확인하고,
어떤 화면이었는지 스크린샷을 남긴 뒤 끝난다.

로그인은 딱 한 번만 시도한다. 반복 실패로 계정이 잠기면 안 되기 때문이다.
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

LOGIN_URL = "https://app.eliteprep.com/login"
SHOT_DIR = "probe-artifacts"


def shot(page, name):
    os.makedirs(SHOT_DIR, exist_ok=True)
    path = os.path.join(SHOT_DIR, name)
    try:
        page.screenshot(path=path, full_page=True)
        print(f"   스크린샷: {path}", flush=True)
    except Exception as e:
        print(f"   스크린샷 실패: {e}", flush=True)


def token(page):
    try:
        return page.evaluate("() => localStorage.getItem('jwt_access_token')")
    except Exception:
        return None


def main():
    email = os.getenv("SRDB_EMAIL")
    password = os.getenv("SRDB_PASSWORD")
    if not (email and password):
        raise SystemExit("[중단] SRDB_EMAIL / SRDB_PASSWORD 시크릿이 필요합니다.")

    from playwright.sync_api import sync_playwright

    print("--- SRDB 클라우드 로그인 실험 ---", flush=True)
    with sync_playwright() as pw:
        # headless=False + xvfb. 진짜 창을 띄우는 것이 이 실험의 핵심이다.
        browser = pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--window-size=1400,900"])
        ctx = browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1400, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"))
        page = ctx.new_page()

        print("[1/3] 로그인 화면 여는 중…", flush=True)
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(15_000)
        shot(page, "1-login-page.png")

        body = (page.inner_text("body") or "")[:400].replace("\n", " | ")
        print(f"   화면: {body}", flush=True)

        if not page.is_visible("#email"):
            print("\n❌ 실패 — 로그인 폼이 나타나지 않았습니다.", flush=True)
            print("   Turnstile 이 이 서버를 막았을 가능성이 높습니다.", flush=True)
            shot(page, "2-no-form.png")
            ctx.close(); browser.close()
            sys.exit(2)

        print("[2/3] 자격 증명 입력 (한 번만 시도)…", flush=True)
        page.fill("#email", email)
        page.fill("#password", password)
        page.click("button[type=submit]")

        print("[3/3] 토큰 대기 (최대 120초)…", flush=True)
        deadline = time.time() + 120
        while time.time() < deadline and not token(page):
            page.wait_for_timeout(2000)

        got = token(page)
        shot(page, "3-after-login.png")
        print(f"   최종 주소: {page.url}", flush=True)

        if got:
            print("\n✅ 성공 — 클라우드에서도 SRDB 로그인이 됩니다.", flush=True)
            print("   명단 갱신도 클라우드로 옮길 수 있습니다 (랩탑 완전 불필요).", flush=True)
            code = 0
        else:
            after = (page.inner_text("body") or "")[:400].replace("\n", " | ")
            print("\n❌ 실패 — 토큰을 받지 못했습니다.", flush=True)
            print(f"   화면: {after}", flush=True)
            print("   랩탑에서 명단을 갱신하는 현재 방식을 유지해야 합니다.", flush=True)
            code = 3

        ctx.close()
        browser.close()
    sys.exit(code)


if __name__ == "__main__":
    main()

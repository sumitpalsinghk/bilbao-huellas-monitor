import os
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

APPOINTMENT_URL = (
    "https://icp.administracionelectronica.gob.es/icpplus/index.html"
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PROVINCE = "Bizkaia"

HUELLAS_TERMS = [
    "TOMA DE HUELLAS",
    "POLICIA - TOMA DE HUELLAS",
    "EXPEDICIÓN DE TARJETA",
    "EXPEDICION DE TARJETA",
]

NO_APPOINTMENT_TERMS = [
    "NO HAY CITAS",
    "NO EXISTEN CITAS",
    "NO HAY DISPONIBILIDAD",
    "NO AVAILABLE APPOINTMENTS",
    "EN ESTE MOMENTO NO HAY CITAS",
]

CAPTCHA_TERMS = [
    "CAPTCHA",
    "RECAPTCHA",
    "VERIFICACIÓN",
    "VERIFICACION",
    "VERIFICATION",
]


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials are not configured.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
        },
        timeout=20,
    )

    response.raise_for_status()
    print("Telegram notification sent.")


def page_text(page):
    try:
        return page.locator("body").inner_text().upper()
    except Exception:
        return ""


def select_option_containing(page, terms):
    selects = page.locator("select")

    print(f"Found {selects.count()} select elements.")

    for i in range(selects.count()):
        select = selects.nth(i)

        try:
            options = select.locator("option")

            for j in range(options.count()):
                option = options.nth(j)
                text = option.inner_text().strip().upper()

                if any(term.upper() in text for term in terms):
                    value = option.get_attribute("value")

                    print(f"Found matching option: {text}")

                    if value:
                        select.select_option(value=value)
                    else:
                        select.select_option(label=option.inner_text())

                    return True

        except Exception as e:
            print(f"Could not inspect select {i}: {e}")

    return False


def click_aceptar(page):
    try:
        buttons = page.get_by_role("button", name="Aceptar")

        if buttons.count() > 0:
            buttons.first.click(timeout=10000)
            print("Clicked Aceptar.")
            return True
    except Exception:
        pass

    try:
        links = page.get_by_text("Aceptar", exact=True)

        if links.count() > 0:
            links.first.click(timeout=10000)
            print("Clicked Aceptar.")
            return True
    except Exception:
        pass

    print("Could not find Aceptar.")
    return False


def navigate_to_site(page):
    for attempt in range(1, 4):
        print(f"Opening appointment website - attempt {attempt}/3...")

        try:
            page.goto(
                APPOINTMENT_URL,
                wait_until="commit",
                timeout=30000,
            )

            print("Initial navigation completed.")

            # Give the government website time to load its JavaScript.
            page.wait_for_timeout(12000)

            text = page_text(page)

            if text:
                print("Page content received.")
                return True

            print("Page loaded but no body text was detected.")

        except PlaywrightTimeoutError as e:
            print(f"Navigation timeout on attempt {attempt}: {e}")

        except Exception as e:
            print(f"Navigation error on attempt {attempt}: {e}")

        if attempt < 3:
            print("Waiting 5 seconds before retry...")
            time.sleep(5)

    return False


def check_appointment(page):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print()
    print("=" * 60)
    print(f"[{now}] Checking Bilbao Toma de Huellas")
    print("=" * 60)

    if not navigate_to_site(page):
        print("❌ Could not reach the official appointment website.")

        try:
            page.screenshot(
                path="website_timeout.png",
                full_page=True,
            )
        except Exception:
            pass

        return "unreachable"

    text = page_text(page)

    print("Initial page text:")
    print(text[:3000])

    if any(term in text for term in CAPTCHA_TERMS):
        print("⚠️ CAPTCHA/human verification detected.")
        return "captcha"

    print()
    print("Selecting province: Bizkaia")

    if not select_option_containing(page, [PROVINCE]):
        print("❌ Could not find Bizkaia in the province selector.")

        try:
            page.screenshot(
                path="debug_bizkaia.png",
                full_page=True,
            )
        except Exception:
            pass

        return "unknown"

    if not click_aceptar(page):
        print("❌ Could not click Aceptar after selecting Bizkaia.")

        try:
            page.screenshot(
                path="debug_accept_bizkaia.png",
                full_page=True,
            )
        except Exception:
            pass

        return "unknown"

    page.wait_for_timeout(5000)

    text = page_text(page)

    print()
    print("After Bizkaia selection:")
    print(text[:4000])

    if any(term in text for term in CAPTCHA_TERMS):
        print("⚠️ CAPTCHA detected.")
        return "captcha"

    print()
    print("Looking for Toma de Huellas procedure...")

    if not select_option_containing(page, HUELLAS_TERMS):
        print("❌ Could not find Toma de Huellas.")

        try:
            page.screenshot(
                path="debug_huellas.png",
                full_page=True,
            )
        except Exception:
            pass

        return "unknown"

    if not click_aceptar(page):
        print("❌ Could not click Aceptar after Toma de Huellas.")

        try:
            page.screenshot(
                path="debug_accept_huellas.png",
                full_page=True,
            )
        except Exception:
            pass

        return "unknown"

    page.wait_for_timeout(5000)

    text = page_text(page)

    print()
    print("Appointment page:")
    print(text[:6000])

    if any(term in text for term in CAPTCHA_TERMS):
        print("⚠️ CAPTCHA detected.")
        return "captcha"

    for term in NO_APPOINTMENT_TERMS:
        if term in text:
            print(f"❌ No appointments detected. Matched: {term}")
            return False

    availability_indicators = [
        "SELECCIONE UNA CITA",
        "SELECCIONE LA CITA",
        "SELECCIONE FECHA",
        "SELECCIONE HORA",
        "CITA DISPONIBLE",
        "CITAS DISPONIBLES",
        "FECHA",
        "HORA",
    ]

    for term in availability_indicators:
        if term in text:
            print(f"🚨 POSSIBLE AVAILABILITY DETECTED: {term}")

            try:
                page.screenshot(
                    path="appointment_available.png",
                    full_page=True,
                )
            except Exception:
                pass

            return True

    print("⚠️ Could not determine appointment availability.")

    try:
        page.screenshot(
            path="debug_final.png",
            full_page=True,
        )
    except Exception:
        pass

    return "unknown"


def main():
    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            },
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        try:
            result = check_appointment(page)

            print()
            print(f"FINAL RESULT: {result}")

            if result is True:

                message = (
                    "🚨 BILBAO HUELLAS ALERT 🚨\n\n"
                    "Possible Toma de Huellas appointment availability "
                    "was detected.\n\n"
                    "Please open the official Spanish appointment website "
                    "and check/book manually."
                )

                send_telegram(message)

            elif result == "unreachable":

                print(
                    "Website could not be reached. "
                    "No Telegram availability alert sent."
                )

            elif result == "captcha":

                print(
                    "Human verification detected. "
                    "No availability alert sent."
                )

            elif result == "unknown":

                print(
                    "The website was reached, but availability "
                    "could not be determined."
                )

            else:

                print("No appointment detected.")

        except Exception as e:

            print(f"UNEXPECTED ERROR: {e}")

        finally:

            browser.close()


if __name__ == "__main__":
    main()

import os
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

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
    "TOMA DE HUELLAS (EXPEDICIÓN DE TARJETA)",
]

NO_APPOINTMENT_TERMS = [
    "NO HAY CITAS",
    "NO EXISTEN CITAS",
    "NO HAY DISPONIBILIDAD",
    "NO AVAILABLE APPOINTMENTS",
]

CAPTCHA_TERMS = [
    "CAPTCHA",
    "RECAPTCHA",
    "VERIFICACIÓN",
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


def select_option_containing(page, terms):
    selects = page.locator("select")

    for i in range(selects.count()):
        select = selects.nth(i)

        try:
            options = select.locator("option")
            for j in range(options.count()):
                text = options.nth(j).inner_text().strip().upper()

                if any(term.upper() in text for term in terms):
                    value = options.nth(j).get_attribute("value")

                    if value:
                        select.select_option(value=value)
                    else:
                        select.select_option(label=options.nth(j).inner_text())

                    return True
        except Exception:
            continue

    return False


def click_aceptar(page):
    buttons = page.get_by_role("button", name="Aceptar")

    if buttons.count() > 0:
        buttons.first.click()
        return True

    links = page.get_by_text("Aceptar", exact=True)

    if links.count() > 0:
        links.first.click()
        return True

    return False


def check_appointment(page):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] Checking Bilbao Toma de Huellas...")

    page.goto(
        APPOINTMENT_URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(4000)

    text = page.locator("body").inner_text().upper()

    # CAPTCHA / human verification
    if any(term in text for term in CAPTCHA_TERMS):
        print("CAPTCHA/human verification detected.")
        return "captcha"

    print("Selecting Bizkaia...")

    if not select_option_containing(page, [PROVINCE]):
        print("Could not find Bizkaia province selector.")
        page.screenshot(path="debug_province.png", full_page=True)
        return "unknown"

    if not click_aceptar(page):
        print("Could not click Aceptar after province.")
        page.screenshot(path="debug_accept_province.png", full_page=True)
        return "unknown"

    page.wait_for_timeout(3000)

    text = page.locator("body").inner_text().upper()

    if any(term in text for term in CAPTCHA_TERMS):
        print("CAPTCHA detected.")
        return "captcha"

    print("Looking for Toma de Huellas procedure...")

    if not select_option_containing(page, HUELLAS_TERMS):
        print("Could not find Toma de Huellas procedure.")
        page.screenshot(path="debug_huellas.png", full_page=True)
        print(text[:5000])
        return "unknown"

    if not click_aceptar(page):
        print("Could not click Aceptar after selecting procedure.")
        page.screenshot(path="debug_accept_huellas.png", full_page=True)
        return "unknown"

    page.wait_for_timeout(3000)

    text = page.locator("body").inner_text().upper()

    if any(term in text for term in CAPTCHA_TERMS):
        print("CAPTCHA detected.")
        return "captcha"

    print(text[:5000])

    # Explicit no-appointment response
    if any(term in text for term in NO_APPOINTMENT_TERMS):
        print("❌ No appointment available.")
        return False

    # Indicators that the appointment calendar/selection is available
    availability_indicators = [
        "SELECCIONE UNA CITA",
        "SELECCIONE LA CITA",
        "SELECCIONE FECHA",
        "SELECCIONE HORA",
        "FECHA",
        "HORA",
        "CITA DISPONIBLE",
        "CITAS DISPONIBLES",
    ]

    if any(term in text for term in availability_indicators):
        print("🚨 POSSIBLE APPOINTMENT AVAILABILITY DETECTED!")
        page.screenshot(path="appointment_available.png", full_page=True)
        return True

    print("⚠️ Could not determine availability.")
    page.screenshot(path="debug_final.png", full_page=True)
    return "unknown"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1440, "height": 1000}
        )

        try:
            result = check_appointment(page)

            if result is True:
                message = (
                    "🚨 BILBAO HUELLAS ALERT 🚨\n\n"
                    "Possible Toma de Huellas appointment availability "
                    "was detected.\n\n"
                    "Open the official appointment website and check "
                    "manually immediately."
                )

                send_telegram(message)

            elif result == "captcha":
                print("CAPTCHA encountered. No alert sent.")

            elif result == "unknown":
                print("Availability could not be confirmed.")

        except Exception as e:
            print(f"ERROR: {e}")

        finally:
            browser.close()


if __name__ == "__main__":
    main()

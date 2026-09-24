import os
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

APPOINTMENT_URL = (
    "https://icp.administracionelectronica.gob.es/icpplus/index.html"
)

CHECK_EVERY_SECONDS = 60

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials are not configured.")
        return

    url = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
        },
        timeout=20,
    )


def check_appointment(page):
    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Checking appointment page..."
    )

    page.goto(
        APPOINTMENT_URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(5000)

    text = page.locator("body").inner_text().lower()

    print(text[:2000])

    # Stop if the site presents a CAPTCHA or similar human verification.
    captcha_words = [
        "captcha",
        "recaptcha",
        "verificación",
        "verification",
    ]

    if any(word in text for word in captcha_words):
        print("Human verification/CAPTCHA detected.")
        return False

    # These are indicators that the appointment process may have
    # available options. The script does NOT book an appointment.
    availability_words = [
        "cita disponible",
        "citas disponibles",
        "disponibilidad",
        "seleccione una cita",
        "appointment available",
    ]

    available = any(word in text for word in availability_words)

    if available:
        return True

    # Common no-availability wording.
    no_availability_words = [
        "no hay citas",
        "no existen citas",
        "no hay disponibilidad",
        "no available appointments",
        "no appointments available",
    ]

    if any(word in text for word in no_availability_words):
        return False

    print("Could not determine availability from page text.")
    return False


def main():
    already_alerted = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        while True:
            try:
                available = check_appointment(page)

                if available and not already_alerted:
                    message = (
                        "🚨 BILBAO HUELLAS ALERT 🚨\n\n"
                        "The appointment page may show availability.\n"
                        "Open the official appointment website and "
                        "check/book manually."
                    )

                    send_telegram(message)
                    already_alerted = True

                elif not available:
                    already_alerted = False

            except Exception as e:
                print(f"Error: {e}")

            print(
                f"Waiting {CHECK_EVERY_SECONDS} seconds before next check..."
            )

            time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    main()

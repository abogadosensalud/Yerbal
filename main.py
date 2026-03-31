import asyncio
import os
from playwright.async_api import async_playwright
import requests

URL = "https://www.remax.com.ar/listings/venta-departamento-3-amb-calle-yerbal-floresta"
XPATH = "/html/body/app-root/public-layout/mat-sidenav-container/mat-sidenav-content/div/div/app-listing-detail/div/div[2]/div/div[1]/qr-card-info-prop/div/div[1]/div[3]/p"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

LAST_PRICE_FILE = "last_price.txt"


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})


def read_last_price():
    if not os.path.exists(LAST_PRICE_FILE):
        return None
    with open(LAST_PRICE_FILE, "r") as f:
        return f.read().strip()


def save_price(price):
    with open(LAST_PRICE_FILE, "w") as f:
        f.write(price)


async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto(URL, timeout=60000)

            # esperar a que cargue algo del DOM
            await page.wait_for_timeout(5000)

            element = await page.query_selector(f'xpath={XPATH}')

            if not element:
                send_telegram("La publicación de la calle Yerbal, ya no está disponible.")
                return

            price = await element.inner_text()
            price = price.strip()

            last_price = read_last_price()

            if last_price:
                # limpiar números
                def clean(p):
                    return int("".join(filter(str.isdigit, p)))

                if clean(price) < clean(last_price):
                    send_telegram("La publicación de la calle Yerbal ha bajado de precio")

            save_price(price)

        except Exception as e:
            send_telegram("Error en scraper: " + str(e))

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape())

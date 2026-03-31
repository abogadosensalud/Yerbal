import asyncio
import os
from playwright.async_api import async_playwright
import requests

URL = "https://www.remax.com.ar/listings/venta-departamento-3-amb-calle-yerbal-floresta"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

LAST_PRICE_FILE = "last_price.txt"


# ------------------------
# TELEGRAM
# ------------------------
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Error enviando Telegram:", e)


# ------------------------
# FILE HANDLING
# ------------------------
def read_last_price():
    if not os.path.exists(LAST_PRICE_FILE):
        return None
    with open(LAST_PRICE_FILE, "r") as f:
        return f.read().strip()


def save_price(price):
    with open(LAST_PRICE_FILE, "w") as f:
        f.write(price)


def normalize(price):
    return int("".join(filter(str.isdigit, price)))


# ------------------------
# SCRAPER
# ------------------------
async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto(URL, timeout=60000)
            await page.wait_for_load_state("networkidle")

            # ------------------------
            # 1. DETECTAR SI NO EXISTE
            # ------------------------
            body = await page.inner_text("body")
            lower = body.lower()

            if (
                "no disponible" in lower
                or "publicación finalizada" in lower
                or "no se encuentra" in lower
                or "404" in lower
            ):
                send_telegram("La publicación de la calle Yerbal, ya no está disponible.")
                return

            # ------------------------
            # 2. BUSCAR PRECIO (FORMA ROBUSTA)
            # ------------------------
            # Este selector apunta al componente real del precio
            locator = page.locator("qr-card-info-prop")

            if await locator.count() == 0:
                print("No se encontró el contenedor del precio")
                return

            text = await locator.first.inner_text()

            # Buscar línea que tenga USD
            lines = text.split("\n")
            price = None

            for line in lines:
                if "USD" in line or "U$S" in line:
                    price = line.strip()
                    break

            if not price:
                print("No se pudo extraer el precio dentro del componente")
                print("Contenido:", text)
                return

            print("Precio actual:", price)

            # ------------------------
            # 3. COMPARAR
            # ------------------------
            last_price = read_last_price()

            if last_price:
                if normalize(price) < normalize(last_price):
                    send_telegram("La publicación de la calle Yerbal ha bajado de precio")

            # ------------------------
            # 4. GUARDAR
            # ------------------------
            save_price(price)

        except Exception as e:
            send_telegram(f"Error en scraper: {str(e)}")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape())

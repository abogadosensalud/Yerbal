import asyncio
import os
import re
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


# ------------------------
# UTIL
# ------------------------
def extract_price(text):
    """
    Busca precios tipo:
    USD 120.000
    U$S 120000
    """
    match = re.search(r"(USD|U\$S)\s?([\d\.]+)", text)
    if match:
        return match.group(0)
    return None


def normalize(price):
    """Convierte 'USD 120.000' -> 120000"""
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

            # 🔍 Obtener todo el texto
            page_text = await page.inner_text("body")
            lower_text = page_text.lower()

            # ------------------------
            # 1. DETECTAR SI NO EXISTE
            # ------------------------
            if (
                "no disponible" in lower_text
                or "publicación finalizada" in lower_text
                or "no se encuentra" in lower_text
                or "404" in lower_text
            ):
                send_telegram("La publicación de la calle Yerbal, ya no está disponible.")
                return

            # ------------------------
            # 2. EXTRAER PRECIO
            # ------------------------
            price = extract_price(page_text)

            if not price:
                print("No se pudo encontrar el precio (posible cambio de DOM)")
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

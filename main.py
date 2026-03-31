import asyncio
import os
from playwright.async_api import async_playwright
import requests

URL = "https://www.remax.com.ar/listings/venta-departamento-3-amb-calle-yerbal-floresta"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

LAST_PRICE_FILE = "last_price.txt"


def log(msg):
    print(f"[LOG] {msg}")


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
        log("Mensaje enviado a Telegram")
    except Exception as e:
        log(f"Error enviando Telegram: {e}")


def read_last_price():
    if not os.path.exists(LAST_PRICE_FILE):
        log("No existe last_price.txt")
        return None
    with open(LAST_PRICE_FILE, "r") as f:
        value = f.read().strip()
        log(f"Último precio guardado: {value}")
        return value


def save_price(price):
    with open(LAST_PRICE_FILE, "w") as f:
        f.write(price)
    log(f"Precio guardado: {price}")


def normalize(price):
    return int("".join(filter(str.isdigit, price)))


async def scrape():
    log("Iniciando scraper...")

    async with async_playwright() as p:
        log("Lanzando navegador...")
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            locale="es-AR",
            timezone_id="America/Argentina/Buenos_Aires"
        )

        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        try:
            log(f"Navegando a {URL}")
            response = await page.goto(URL, timeout=60000)

            if response:
                log(f"Status HTTP: {response.status}")
            else:
                log("No hubo response")

            log("Esperando render...")
            await page.wait_for_timeout(8000)

            log("Tomando screenshot...")
            await page.screenshot(path="debug.png")

            log("Guardando HTML...")
            html = await page.content()
            with open("debug.html", "w", encoding="utf-8") as f:
                f.write(html)

            log("Extrayendo texto del body...")
            body = await page.inner_text("body")
            log(f"Body length: {len(body)}")

            lower = body.lower()

            # ------------------------
            # DETECTAR BLOQUEO
            # ------------------------
            if "captcha" in lower:
                log("Detectado CAPTCHA")
                return

            if "access denied" in lower:
                log("Access denied detectado")
                return

            # ------------------------
            # DETECTAR PUBLICACIÓN CAÍDA
            # ------------------------
            if (
                "no disponible" in lower
                or "publicación finalizada" in lower
                or "no se encuentra" in lower
                or "404" in lower
            ):
                log("Detectada publicación no disponible")
                send_telegram("La publicación de la calle Yerbal, ya no está disponible.")
                return

            # ------------------------
            # BUSCAR PRECIO
            # ------------------------
            log("Buscando selector #price-container p ...")
            locator = page.locator("#price-container p")

            count = await locator.count()
            log(f"Cantidad de nodos encontrados: {count}")

            if count == 0:
                log("❌ No se encontró el precio (posible bloqueo o cambio de DOM)")
                return

            price = await locator.first.inner_text()
            price = price.strip()

            log(f"Precio encontrado: {price}")

            # ------------------------
            # COMPARAR
            # ------------------------
            last_price = read_last_price()

            if last_price:
                if normalize(price) < normalize(last_price):
                    log("Precio bajó")
                    send_telegram("La publicación de la calle Yerbal ha bajado de precio")
                else:
                    log("El precio no bajó")

            # ------------------------
            # GUARDAR
            # ------------------------
            save_price(price)

        except Exception as e:
            log(f"ERROR GENERAL: {str(e)}")

        finally:
            log("Cerrando navegador")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape())

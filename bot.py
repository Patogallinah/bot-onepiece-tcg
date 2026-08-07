import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import os
import re

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PREMIUM_BANDAI_URL = "https://p-bandai.com/us/brand/onepiececardgame"

PRODUCTS_FILE = "productos_anteriores.json"

# ==================== FUNCIONES ====================

def obtener_productos():
    """
    Extrae los productos One Piece TCG de Premium Bandai USA usando pyppeteer
    """
    import asyncio
    from pyppeteer import launch
    
    async def scrape():
        browser = await launch(headless=True, args=['--no-sandbox'])
        page = await browser.newPage()
        await page.goto(PREMIUM_BANDAI_URL, waitUntil='networkidle2')
        
        try:
            await page.waitForSelector('a[href*="/us/item/N"]', timeout=5000)
        except:
            print("Timeout esperando productos")
        
        html = await page.content()
        await browser.close()
        return html
    
    try:
        html = asyncio.run(scrape())
        soup = BeautifulSoup(html, 'html.parser')
        
        productos = []
        producto_links = soup.find_all('a', href=lambda x: x and '/us/item/N' in str(x))
        
        print(f"DEBUG: Encontrados {len(producto_links)} enlaces de productos")
        
        for link in producto_links:
            try:
                url = link.get('href', '')
                if url and not url.startswith('http'):
                    url = 'https://p-bandai.com' + url
                
                texto_completo = link.get_text(strip=True)
                nombre = texto_completo[:100] if texto_completo else "Sin nombre"
                
                precio = "N/A"
                precios = re.findall(r'[\d,]+\.\d{2}', texto_completo)
                if precios:
                    precio = precios[0]
                
                estado = "Available"
                es_preventa = False
                if 'PRE-ORDER' in texto_completo.upper():
                    estado = "PRE-ORDER"
                    es_preventa = True
                elif 'OUT OF STOCK' in texto_completo.upper():
                    estado = "OUT OF STOCK"
                
                producto = {
                    'nombre': nombre[:80],
                    'url': url,
                    'precio': precio,
                    'estado': estado,
                    'es_preventa': es_preventa,
                    'timestamp': datetime.now().isoformat()
                }
                
                productos.append(producto)
                
            except Exception as e:
                print(f"Error procesando producto: {e}")
                continue
        
        return productos
    
    except Exception as e:
        print(f"Error obteniendo productos: {e}")
        return []
def cargar_productos_anteriores():
    """Carga productos del monitoreo anterior"""
    if os.path.exists(PRODUCTS_FILE):
        try:
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

# ====================

def guardar_productos(productos):
    """Guarda productos para próxima comparación"""
    try:
        with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(productos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando productos: {e}")

# ====================

def detectar_cambios(productos_nuevos, productos_anteriores):
    """Detecta nuevos productos y preventas"""
    cambios = {
        'nuevos': [],
        'preventas_nuevas': []
    }
    
    nombres_anteriores = {p['nombre'] for p in productos_anteriores}
    
    for producto in productos_nuevos:
        if producto['nombre'] not in nombres_anteriores:
            cambios['nuevos'].append(producto)
        
        if producto['es_preventa']:
            previo = next((p for p in productos_anteriores 
                          if p['nombre'] == producto['nombre']), None)
            if not previo or not previo.get('es_preventa', False):
                cambios['preventas_nuevas'].append(producto)
    
    return cambios
    
# ====================

def enviar_telegram(mensaje):
    """Envía mensaje a Telegram usando requests"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': int(CHAT_ID),
            'text': mensaje,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            print("✅ Mensaje enviado a Telegram")
            return True
        else:
            print(f"❌ Error Telegram: {response.text}")
            return False
    except Exception as e:
        print(f"Error enviando Telegram: {e}")
        return False

# ====================

def formatear_alerta(cambios):
    """Crea mensaje para Telegram"""
    if not cambios['nuevos'] and not cambios['preventas_nuevas']:
        return None
    
    mensaje = "🎴 <b>ALERTA ONE PIECE TCG - Premium Bandai USA</b>\n\n"
    
    if cambios['nuevos']:
        mensaje += "🆕 <b>NUEVOS PRODUCTOS:</b>\n"
        for p in cambios['nuevos'][:5]:
            mensaje += f"• <b>{p['nombre']}</b>\n"
            mensaje += f"  💰 {p['precio']}\n"
            if p['url']:
                mensaje += f"  🔗 <a href=\"{p['url']}\">Ver</a>\n"
            mensaje += "\n"
    
    if cambios['preventas_nuevas']:
        mensaje += "⏰ <b>NUEVAS PREVENTAS:</b>\n"
        for p in cambios['preventas_nuevas'][:5]:
            mensaje += f"• <b>{p['nombre']}</b>\n"
            mensaje += f"  💰 {p['precio']}\n"
            if p['url']:
                mensaje += f"  🔗 <a href=\"{p['url']}\">Ver</a>\n"
            mensaje += "\n"
    
    mensaje += f"⏰ Última revisión: {datetime.now().strftime('%H:%M:%S')}"
    return mensaje

# ====================

def ejecutar_ciclo():
    """Ejecuta UN ciclo de monitoreo"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando monitoreo...")
    
    productos_nuevos = obtener_productos()
    if not productos_nuevos:
        print("❌ No se pudieron obtener productos")
        return
    
    print(f"✅ Se obtuvieron {len(productos_nuevos)} productos")
    
    productos_anteriores = cargar_productos_anteriores()
    cambios = detectar_cambios(productos_nuevos, productos_anteriores)
    
    if cambios['nuevos'] or cambios['preventas_nuevas']:
        mensaje = formatear_alerta(cambios)
        if mensaje:
            print(f"📬 Enviando alertas...")
            enviar_telegram(mensaje)
    else:
        print("ℹ️ Sin cambios detectados")
    
    guardar_productos(productos_nuevos)

# ==================== MAIN ====================

if __name__ == "__main__":
    print("🤖 BOT ONE PIECE TCG INICIADO")
    print("URL: Premium Bandai USA")
    print(f"Ejecutando cada 30 minutos\n")
    
    while True:
        try:
            ejecutar_ciclo()
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("⏳ Esperando 30 minutos...")
        time.sleep(1800)

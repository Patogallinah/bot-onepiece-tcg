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

PREMIUM_BANDAI_URLS = [
    "https://p-bandai.com/us/brand/onepiececardgame",
    "https://p-bandai.com/us/series/onepiece-series?_f_series=03-002&offset=0&limit=20&sortType=NewArrival&_f_productStatuses=Waiting,On"
]

PRODUCTS_FILE = "productos_anteriores.json"

# ==================== FUNCIONES ====================

def obtener_productos():
    """Extrae los productos One Piece TCG de Premium Bandai USA"""
    import cloudscraper
    
    try:
        scraper = cloudscraper.create_scraper()
        productos = []
        
        for url in PREMIUM_BANDAI_URLS:
            try:
                response = scraper.get(url, timeout=15)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.content, 'html.parser')
                
                producto_links = soup.find_all('a', href=lambda x: x and '/item/' in str(x))
                print(f"DEBUG: Encontrados {len(producto_links)} enlaces en {url.split('?')[0]}")
                
                for link in producto_links:
                    try:
                        url_producto = link.get('href', '')
                        if url_producto and not url_producto.startswith('http'):
                            url_producto = 'https://p-bandai.com' + url_producto
                        
                        texto_completo = link.get_text(strip=True)
                        nombre = texto_completo[:100] if texto_completo else "Sin nombre"
                        
                        if not nombre or len(nombre) < 5:
                            continue
                        if 'CARD GAME' not in nombre.upper() and 'TCG' not in nombre.upper():
                            continue
                        
                        precio = "N/A"
                        precios = re.findall(r'[\d,]+\.\d{2}', texto_completo)
                        if precios:
                            precio = precios[0]
                        
                        estado = "Available"
                        es_preventa = False
                        if 'PRE-ORDER' in texto_completo.upper() or 'WAITING' in texto_completo.upper():
                            estado = "PRE-ORDER"
                            es_preventa = True
                        elif 'OUT OF STOCK' in texto_completo.upper():
                            estado = "OUT OF STOCK"
                        
                        producto = {
                            'nombre': nombre[:80],
                            'url': url_producto,
                            'precio': precio,
                            'estado': estado,
                            'es_preventa': es_preventa,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        if not any(p['nombre'] == producto['nombre'] for p in productos):
                            productos.append(producto)
                        
                    except Exception as e:
                        continue
            
            except Exception as e:
                print(f"Error en URL: {e}")
                continue
        
        print(f"✅ Total productos: {len(productos)}")
        return productos
    
    except Exception as e:
        print(f"Error obteniendo productos: {e}")
        return []

def cargar_productos_anteriores():
    """Carga productos anteriores"""
    if os.path.exists(PRODUCTS_FILE):
        try:
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def guardar_productos(productos):
    """Guarda productos"""
    try:
        with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(productos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando: {e}")

def detectar_cambios(productos_nuevos, productos_anteriores):
    """Detecta cambios"""
    cambios = {'nuevos': [], 'preventas_nuevas': []}
    nombres_anteriores = {p['nombre'] for p in productos_anteriores}
    
    for producto in productos_nuevos:
        if producto['nombre'] not in nombres_anteriores:
            cambios['nuevos'].append(producto)
        
        if producto['es_preventa']:
            previo = next((p for p in productos_anteriores if p['nombre'] == producto['nombre']), None)
            if not previo or not previo.get('es_preventa', False):
                cambios['preventas_nuevas'].append(producto)
    
    return cambios

def enviar_telegram(mensaje):
    """Envía a Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {'chat_id': int(CHAT_ID), 'text': mensaje, 'parse_mode': 'HTML'}
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ Mensaje enviado")
            return True
        return False
    except Exception as e:
        print(f"Error Telegram: {e}")
        return False

def formatear_alerta(cambios):
    """Formatea alerta"""
    if not cambios['nuevos'] and not cambios['preventas_nuevas']:
        return None
    
    mensaje = "🎴 <b>ALERTA ONE PIECE TCG</b>\n\n"
    
    if cambios['nuevos']:
        mensaje += "🆕 <b>NUEVOS:</b>\n"
        for p in cambios['nuevos'][:5]:
            mensaje += f"• {p['nombre']}\n💰 {p['precio']}\n"
    
    if cambios['preventas_nuevas']:
        mensaje += "\n⏰ <b>PREVENTAS:</b>\n"
        for p in cambios['preventas_nuevas'][:5]:
            mensaje += f"• {p['nombre']}\n💰 {p['precio']}\n"
    
    return mensaje

def ejecutar_ciclo():
    """Ejecuta ciclo"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Monitoreo...")
    
    productos_nuevos = obtener_productos()
    if not productos_nuevos:
        print("❌ Sin productos")
        return
    
    productos_anteriores = cargar_productos_anteriores()
    cambios = detectar_cambios(productos_nuevos, productos_anteriores)
    
    if cambios['nuevos'] or cambios['preventas_nuevas']:
        mensaje = formatear_alerta(cambios)
        if mensaje:
            enviar_telegram(mensaje)
    else:
        print("ℹ️ Sin cambios")
    
    guardar_productos(productos_nuevos)

# ==================== MAIN ====================

if __name__ == "__main__":
    print("🤖 BOT ONE PIECE TCG INICIADO")
    print("Ejecutando cada 30 minutos\n")
    
    while True:
        try:
            ejecutar_ciclo()
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("⏳ Esperando 30 min...")
        time.sleep(1800)

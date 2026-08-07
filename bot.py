import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import os
from telegram import Bot
from telegram.error import TelegramError

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = "890123456789:ABCDEfghijklmnOPqrstUVwxyz"  # TU TOKEN
CHAT_ID = "5422921883"  # TU CHAT ID
PREMIUM_BANDAI_URL = "https://p-bandai.com/b-boys-log/search.html?search_word=one%20piece%20card%20game"

PRODUCTS_FILE = "productos_anteriores.json"

# ==================== FUNCIONES ====================

def obtener_productos():
    """
    Extrae los productos One Piece TCG de Premium Bandai
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(PREMIUM_BANDAI_URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        productos = []
        
        # Buscar items en la página
        items = soup.find_all('div', class_='item')
        
        for item in items:
            try:
                nombre = item.find('a', class_='item-name')
                precio = item.find('span', class_='price')
                estado = item.find('span', class_='status')
                
                if nombre:
                    es_preventa = False
                    if estado and 'preventa' in estado.text.lower():
                        es_preventa = True
                    
                    producto = {
                        'nombre': nombre.text.strip(),
                        'url': nombre.get('href', ''),
                        'precio': precio.text.strip() if precio else 'N/A',
                        'estado': estado.text.strip() if estado else 'Disponible',
                        'es_preventa': es_preventa,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    productos.append(producto)
            except Exception as e:
                print(f"Error procesando item: {e}")
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

def guardar_productos(productos):
    """Guarda productos para próxima comparación"""
    try:
        with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(productos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando productos: {e}")

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

def enviar_telegram(mensaje):
    """Envía mensaje a Telegram"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        bot.send_message(chat_id=CHAT_ID, text=mensaje, parse_mode='HTML')
        return True
    except TelegramError as e:
        print(f"Error enviando Telegram: {e}")
        return False

def formatear_alerta(cambios):
    """Crea mensaje para Telegram"""
    if not cambios['nuevos'] and not cambios['preventas_nuevas']:
        return None
    
    mensaje = "🎴 <b>ALERTA ONE PIECE TCG - Premium Bandai</b>\n\n"
    
    if cambios['nuevos']:
        mensaje += "🆕 <b>NUEVOS PRODUCTOS:</b>\n"
        for p in cambios['nuevos'][:5]:
            mensaje += f"• <b>{p['nombre']}</b>\n"
            mensaje += f"  💰 {p['precio']}\n"
            if p['url']:
                mensaje += f"  🔗 <a href=\"{p['url']}\">Ver</a>\n"
    
    if cambios['preventas_nuevas']:
        mensaje += "\n⏰ <b>NUEVAS PREVENTAS:</b>\n"
        for p in cambios['preventas_nuevas'][:5]:
            mensaje += f"• <b>{p['nombre']}</b>\n"
            mensaje += f"  💰 {p['precio']}\n"
            if p['url']:
                mensaje += f"  🔗 <a href=\"{p['url']}\">Ver</a>\n"
    
    mensaje += f"\n⏰ Última revisión: {datetime.now().strftime('%H:%M:%S')}"
    return mensaje

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
            if enviar_telegram(mensaje):
                print("✅ Alerta enviada a Telegram")
            else:
                print("❌ Error enviando alerta")
    else:
        print("ℹ️ Sin cambios detectados")
    
    guardar_productos(productos_nuevos)

# ==================== MAIN ====================

if __name__ == "__main__":
    print("🤖 BOT ONE PIECE TCG INICIADO")
    print(f"Ejecutando cada 30 minutos\n")
    
    while True:
        try:
            ejecutar_ciclo()
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("⏳ Esperando 30 minutos...")
        time.sleep(1800)

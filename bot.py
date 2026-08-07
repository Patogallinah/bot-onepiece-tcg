import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import os
# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PREMIUM_BANDAI_URL = "https://p-bandai.com/us/brand/onepiececardgame"

PRODUCTS_FILE = "productos_anteriores.json"

# ==================== FUNCIONES ====================

def obtener_productos():
    """
    Extrae los productos One Piece TCG de Premium Bandai USA
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(PREMIUM_BANDAI_URL, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        productos = []
        
        # Buscar todos los links de productos (están en <a> tags dentro de listas)
        # Premium Bandai estructura: link -> images, name, price, status
        
        # Secciones de productos: "New Arrivals", "In-Stock", "Closing Soon"
        producto_links = soup.find_all('a', href=lambda x: x and '/us/item/N' in str(x))
        
        for link in producto_links:
            try:
                # Extraer nombre del producto
                nombre_elem = link.find('generic')  # Primer <generic> contiene el nombre
                if not nombre_elem:
                    continue
                
                nombre = nombre_elem.get_text(strip=True)
                if not nombre:
                    continue
                
                # Extraer precio
                precio = "N/A"
                precio_elems = link.find_all('generic')
                for elem in precio_elems:
                    texto = elem.get_text(strip=True)
                    if texto and any(char.isdigit() for char in texto) and '.' in texto:
                        precio = texto
                        break
                
                # Extraer estado (OUT OF STOCK, PRE-ORDER, etc)
                estado = "Available"
                status_elem = link.find('listitem')
                if status_elem:
                    estado = status_elem.get_text(strip=True)
                
                # Detectar si es preventa
                es_preventa = 'PRE-ORDER' in estado.upper() or 'WAITING' in estado.upper()
                
                url = link.get('href', '')
                if url and not url.startswith('http'):
                    url = 'https://p-bandai.com' + url
                
                producto = {
                    'nombre': nombre,
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
        # Producto completamente nuevo
        if producto['nombre'] not in nombres_anteriores:
            cambios['nuevos'].append(producto)
        
        # Producto que ahora está en preventa
        if producto['es_preventa']:
            previo = next((p for p in productos_anteriores 
                          if p['nombre'] == producto['nombre']), None)
            if not previo or not previo.get('es_preventa', False):
                cambios['preventas_nuevas'].append(producto)
    
    return cambios

def enviar_telegram(mensaje):
    """Envía mensaje a Telegram usando requests (sin async)"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': CHAT_ID,
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
                mensaje += f"  🔗 <a href=\"{p['url']}\">Ver producto</a>\n"
            mensaje += "\n"
    
    if cambios['preventas_nuevas']:
        mensaje += "⏰ <b>NUEVAS PREVENTAS:</b>\n"
        for p in cambios['preventas_nuevas'][:5]:
            mensaje += f"• <b>{p['nombre']}</b>\n"
            mensaje += f"  💰 {p['precio']}\n"
            if p['url']:
                mensaje += f"  🔗 <a href=\"{p['url']}\">Ver producto</a>\n"
            mensaje += "\n"
    
    mensaje += f"⏰ Última revisión: {datetime.now().strftime('%H:%M:%S %Z')}"
    return mensaje

def ejecutar_ciclo():
    """Ejecuta UN ciclo de monitoreo"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando monitoreo...")
    
    productos_nuevos = obtener_productos()
    if not productos_nuevos:
        print("❌ No se pudieron obtener productos")
        enviar_telegram("⚠️ El bot no pudo extraer productos de Premium Bandai. Verifica la estructura HTML.")
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
    print("URL: Premium Bandai USA")
    print(f"Ejecutando cada 30 minutos\n")
    
    while True:
        try:
            ejecutar_ciclo()
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("⏳ Esperando 30 minutos...")
        time.sleep(1800)

# Dependencias de firebase
import firebase_admin
from firebase_admin import credentials, db

# Importamos Telegram
import telebot
from telebot import types

# Llamadas al sistema e integraciones externas
import os
import sys
import signal
import requests
import json
import threading
import time
from collections import deque

# Gestión de ficheros
from pathlib import Path

# Utilidades Python
from enum import Enum

################### Importar clases extra

# Validadores
from validators.OfferValidator import OfferValidator

##############################################################################
####################### Variables globales ###################################
##############################################################################

class TipoOferta(Enum):
    DISPOSITIVO = "device"
    TARIFA = "plan"

##############################################################################
####################### Inicialización Funciones Bot Telegram ################
##############################################################################

script_dir = Path(__file__).parent

# Token de acceso del bot proporcionado por BotFather
TOKEN = None

ruta_token = os.path.join(f'{script_dir}/keys', 'telegram_token.txt')

try:
    with open(ruta_token, 'r') as archivo:
        TOKEN = archivo.read().strip()
        
    if not TOKEN:
        raise ValueError("El archivo del token está vacío.")
        
except FileNotFoundError:
    print(f"[ERROR] No se ha encontrado el archivo del token en {ruta_token}")
    exit(1)
except Exception as e:
    print(f"[ERROR] Error al leer el token: {e}")
    exit(1)

# Diccionario para rastrear qué botones se han presionado por chat_id
pressed_buttons = {}

# Inicializamos un diccionario que contenga los detalles del pedido
descripcionPedido = {}

# Oferta que se está atendiendo en cada chat: {chat_id: oferta_id}
oferta_activa = {}

# Ofertas a la espera de que el cliente termine la que tiene activa: {chat_id: deque[(oferta_id, oferta_data)]}
ofertas_pendientes = {}

# Las ofertas llegan desde el hilo del listener de Firebase y se cierran desde los hilos de Telegram
lock_ofertas = threading.Lock()

# Inicializa el bot con el token
bot = telebot.TeleBot(TOKEN)

##############################################################################
####################### FUNCIONES ANALYTICS Y EMAILS #########################
##############################################################################

def get_firebase_uid(chat_id):
    """
    Busca el UID de Firebase asociado a un chat_id de Telegram en la RTDB.
    """
    try:
        ref_telegram = db.reference('telegram')
        resultados = ref_telegram.order_by_value().equal_to(chat_id).get()
        
        if resultados:
            # Extraemos la primera clave encontrada, que es el UID
            return list(resultados.keys())[0]
            
    except Exception as e:
        print(f"[ERROR] Fallo al consultar el nodo 'telegram' en RTDB: {e}")
    
    return str(chat_id) # Fallback

def queue_email(chat_id, code_event):
    """
    Envía un evento a la cola de procesamiento de emails en Firebase RTDB.
    Esto será recogido por n8n para enviar el correo correspondiente.
    """
    uid_fb = get_firebase_uid(chat_id)
    
    email_data = {
        "uid_fb": uid_fb,
        "code": code_event
    }
    
    try:
        ref_emails = db.reference('cola_procesamiento/emails')
        ref_emails.push(email_data)
        print(f"[INFO] Evento de email '{code_event}' encolado para el usuario {uid_fb}.")
    except Exception as e:
        print(f"[ERROR] Error al encolar email en Firebase: {e}")

def send_analytics_event(client_id, event_name, motivo):
    """
    Lee variables de entorno para usar Google Analytics 4 (GA4).
    """
    api_secret = os.getenv("GA_API_SECRET")
    measurement_id = os.getenv("GA_MEASUREMENT_ID")

    if not api_secret or not measurement_id:
        print("[WARN] Credenciales GA4 no encontradas en el entorno. Omitiendo analítica.")
        return

    firebase_uid = get_firebase_uid(client_id)

    # 2. Envío a GA4
    url = f"https://www.google-analytics.com/mp/collect?measurement_id={measurement_id}&api_secret={api_secret}"

    payload = {
        "client_id": firebase_uid, 
        "user_id": firebase_uid,
        "events": [{
            "name": event_name,
            "params": {
                "motivo": motivo,
                "plataforma": "telegram"
            }
        }]
    }

    try:
        # Añadimos un timeout corto para no bloquear el hilo del bot si GA4 tarda
        response = requests.post(url, data=json.dumps(payload), timeout=3)
        # GA4 suele devolver 204 No Content cuando el envío es correcto
        if response.status_code in [200, 204]:
            print(f"[INFO] Analítica '{event_name}' ({motivo}) enviada a GA4 con UID {firebase_uid}.")
        else:
            print(f"[WARN] Error HTTP de GA4: {response.status_code}\n{response.text}")
    except Exception as e:
        print(f"[ERROR] Excepción de red enviando a GA4: {e}")

# Maneja el comando '/start'
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "¡Bienvenido! Has contactado con el bot de asistencia de TeleUPM 🤖, tu empresa favorita de telefonía y redes móviles")
    print(message.chat.id)


##############################################################################
####################### PREGUNTAS DISPOSITIVOS ###############################
##############################################################################

def ask_rom(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('128GB', callback_data=f"{TipoOferta.DISPOSITIVO.value},pedir_almacenamiento,alm1,128GB")
    btn2 = types.InlineKeyboardButton('256GB', callback_data=f"{TipoOferta.DISPOSITIVO.value},pedir_almacenamiento,alm2,256GB")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "Antes que nada, necesito saber las características que deseas obtener en tu dispositivo")
    bot.send_message(message.chat.id, "Recuerda que el almacenamiento de un dispositivo móvil mide la cantidad de fotos, vídeos, música y aplicaciones que puedes guardar en tu dispositivo y se mide en Gigas (GB). Un Gigabyte equivale a 300 fotos en alta calidad aproximadamente")
    bot.send_message(message.chat.id, "¿Cuál es tu configuración de almacenamiento preferida?", reply_markup=markup)

def ask_color(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('⚫ Negro', callback_data=f"{TipoOferta.DISPOSITIVO.value},pedir_color,color1,negro")
    btn2 = types.InlineKeyboardButton('🔵 Azul', callback_data=f"{TipoOferta.DISPOSITIVO.value},pedir_color,color2,azul")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "¿En qué color te gustaría obtener tu nuevo dispositivo?", reply_markup=markup)

def ask_confirmation_device(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('❌ Detener proceso', callback_data=f"{TipoOferta.DISPOSITIVO.value},confirmar_pedido,offer_no_confirm")
    btn2 = types.InlineKeyboardButton('✔ Aceptar y enviar', callback_data=f"{TipoOferta.DISPOSITIVO.value},confirmar_pedido,offer_confirm")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "¿Es todo correcto? Si es así, dará comienzo el proceso de envío 😄", reply_markup=markup)


##############################################################################
####################### PREGUNTAS TARIFAS ####################################
##############################################################################

def ask_permanencia(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('🔓 Sin permanencia', callback_data=f"{TipoOferta.TARIFA.value},pedir_permanencia,perm1,Sin permanencia")
    btn2 = types.InlineKeyboardButton('🔒 12 Meses', callback_data=f"{TipoOferta.TARIFA.value},pedir_permanencia,perm2,12 meses")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "Para adaptar la tarifa a tus necesidades, necesitamos configurar el contrato.")
    bot.send_message(message.chat.id, "¿Prefieres libertad total sin ataduras, o comprometerte 12 meses a cambio de obtener condiciones ventajosas a futuro?", reply_markup=markup)

def ask_extras(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('📱 MultiSIM', callback_data=f"{TipoOferta.TARIFA.value},pedir_extras,ext1,MultiSIM")
    btn2 = types.InlineKeyboardButton('🌍 Bono Internacional', callback_data=f"{TipoOferta.TARIFA.value},pedir_extras,ext2,Bono Internacional")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "¿Qué servicio adicional te gustaría añadir a tu tarifa de forma gratuita durante el primer mes?", reply_markup=markup)

def ask_confirmation_plan(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('❌ Cancelar activación', callback_data=f"{TipoOferta.TARIFA.value},confirmar_pedido,offer_no_confirm")
    btn2 = types.InlineKeyboardButton('✔ Confirmar y activar', callback_data=f"{TipoOferta.TARIFA.value},confirmar_pedido,offer_confirm")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "¿Es todo correcto? Si es así, procederemos a activar tu nueva tarifa en nuestros sistemas", reply_markup=markup)


##############################################################################
####################### CALLBACKS DISPOSITIVOS ###############################
##############################################################################

@bot.callback_query_handler(func=lambda call: call.data.split(',')[0] == TipoOferta.DISPOSITIVO.value)
def callback_query_device(call):
    chat_id = call.message.chat.id
    
    if call.data and pressed_buttons.get(chat_id, False):
        parametros = call.data.split(',')
        grupoBotones = parametros[1]
        boton = parametros[2]

        if len(parametros) == 4:
            infoBoton = parametros[3]

        if grupoBotones in pressed_buttons[chat_id][TipoOferta.DISPOSITIVO.value] and pressed_buttons[chat_id][TipoOferta.DISPOSITIVO.value][grupoBotones] == True:
            bot.answer_callback_query(call.id, text="Ya has seleccionado una opción.")
            return

        if boton == "ofr_yes":
            send_analytics_event(chat_id, "oferta_dispositivo_aceptada", "aceptada_inicio")
            bot.send_message(chat_id, "¡Buena decisión! Comenzemos el proceso de envío")
            ask_rom(call.message)
            
        elif boton == "ofr_no":
            # JOURNEY: Cancelación de dispositivo en la primera pregunta
            send_analytics_event(chat_id, "oferta_dispositivo_cancelada", "cancelada_inicio")
            queue_email(chat_id, "oferta_rechazada_inicio") # NUEVO: Trigger de email
            bot.send_message(chat_id, "¡Sin problema! Te mantendremos informado de las últimas ofertas que te puedan resultar interesantes 😉")
            finalizar_oferta(chat_id)
            return

        elif (boton == "alm1") | (boton == "alm2"):
            descripcionPedido[chat_id]["storage"] = infoBoton
            bot.send_message(chat_id, "¡Estupendo!")
            ask_color(call.message)
            
        elif (boton == "color1") | (boton == "color2"):
            descripcionPedido[chat_id]["color"] = infoBoton
            bot.send_message(chat_id, "¡Genial! Buena elección 😉")
            ask_confirmation_device(call.message)
            
        elif (boton == "offer_confirm"):
            # JOURNEY: Aceptación final del dispositivo
            send_analytics_event(chat_id, "oferta_dispositivo_aceptada", "aceptada_final")
            send_device_data(chat_id)
            bot.send_message(chat_id, "¡Perfecto! Tu pedido será enviado en breve a la dirección que proporcionaste a Tele UPM. Muchas gracias por confiar en nosotros 😄")
            finalizar_oferta(chat_id)
            return

        elif (boton == "offer_no_confirm"):
            # JOURNEY: Cancelación de dispositivo al final del proceso
            send_analytics_event(chat_id, "oferta_dispositivo_cancelada", "cancelada_final")
            queue_email(chat_id, "oferta_cancelada_final") # NUEVO: Trigger de email
            bot.send_message(chat_id, "¡Sin problema! Te mantendremos informado de las últimas ofertas relevantes 😄")
            finalizar_oferta(chat_id)
            return

        if ( grupoBotones != "confirmar_pedido" ):
            pressed_buttons[chat_id][TipoOferta.DISPOSITIVO.value][grupoBotones] = True


##############################################################################
####################### CALLBACKS TARIFAS ####################################
##############################################################################

@bot.callback_query_handler(func=lambda call: call.data.split(',')[0] == TipoOferta.TARIFA.value)
def callback_query_plan(call):
    if call.data:
        chat_id = call.message.chat.id
        parametros = call.data.split(',')
        grupoBotones = parametros[1]
        boton = parametros[2]

        if len(parametros) == 4:
            infoBoton = parametros[3]

        if chat_id in pressed_buttons and grupoBotones in pressed_buttons[chat_id][TipoOferta.TARIFA.value] and pressed_buttons[chat_id][TipoOferta.TARIFA.value][grupoBotones] == True:
            bot.answer_callback_query(call.id, text="Ya has seleccionado una opción.")
            return

        if boton == "ofr_yes":
            send_analytics_event(chat_id, "oferta_tarifa_aceptada", "aceptada_inicio")
            bot.send_message(chat_id, "¡Buena decisión! Comenzemos el proceso de personalización de tu tarifa.")
            ask_permanencia(call.message)
            
        elif boton == "ofr_no":
            # JOURNEY: Cancelación de tarifa en la primera pregunta
            send_analytics_event(chat_id, "oferta_tarifa_cancelada", "cancelada_inicio")
            queue_email(chat_id, "oferta_rechazada_inicio") # NUEVO: Trigger de email
            bot.send_message(chat_id, "¡Sin problema! Te mantendremos informado de las últimas ofertas que te puedan resultar interesantes 😉")
            finalizar_oferta(chat_id)
            return

        elif (boton == "perm1") | (boton == "perm2"):
            descripcionPedido[chat_id]["permanencia"] = infoBoton
            bot.send_message(chat_id, "¡Anotado!")
            ask_extras(call.message)
            
        elif (boton == "ext1") | (boton == "ext2"):
            descripcionPedido[chat_id]["extras"] = infoBoton
            bot.send_message(chat_id, "¡Genial! Una buena decisión 😉")
            ask_confirmation_plan(call.message)
            
        elif (boton == "offer_confirm"):
            # JOURNEY: Aceptación final de la tarifa
            send_analytics_event(chat_id, "oferta_tarifa_aceptada", "aceptada_final")
            send_plan_data(chat_id)
            bot.send_message(chat_id, "¡Perfecto! Tu nueva tarifa ha sido procesada y se activará en tu línea en los próximos minutos. ¡A disfrutar! 🎉")
            finalizar_oferta(chat_id)
            return

        elif (boton == "offer_no_confirm"):
            # JOURNEY: Cancelación de tarifa al final del proceso
            send_analytics_event(chat_id, "oferta_tarifa_cancelada", "cancelada_final")
            queue_email(chat_id, "oferta_cancelada_final") # NUEVO: Trigger de email
            bot.send_message(chat_id, "Operación cancelada. Si cambias de opinión, ¡estaremos por aquí! 😄")
            finalizar_oferta(chat_id)
            return

        if ( grupoBotones != "confirmar_pedido" ):
            pressed_buttons[chat_id][TipoOferta.TARIFA.value][grupoBotones] = True


##############################################################################
####################### Definición de funciones de API #######################
##############################################################################

def send_device_data(chat_id):
    datos_pedido = {
        "user_id": chat_id,
        "type": "telegram",
        "order_type": "device",
        "device_model": descripcionPedido[chat_id]["device_model"],
        "storage": descripcionPedido[chat_id]["storage"],
        "color": descripcionPedido[chat_id]["color"],
        "fecha": {".sv": "timestamp"}
    }
    
    ref_pedidos = db.reference('cola_procesamiento/pedidos')
    print(datos_pedido)
    ref_pedidos.push(datos_pedido)


def send_plan_data(chat_id):
    datos_tarifa = {
        "user_id": chat_id,
        "type": "telegram",
        "order_type": "plan",
        "plan": descripcionPedido[chat_id]["plan"], 
        "permanencia": descripcionPedido[chat_id]["permanencia"],
        "extras": descripcionPedido[chat_id]["extras"],
        "fecha": {".sv": "timestamp"}
    }
    
    ref_tarifas = db.reference('cola_procesamiento/pedidos')
    print(datos_tarifa)
    ref_tarifas.push(datos_tarifa)

def send_device_offer(oferta):
    chat_id = oferta.get("chat_id")

    pressed_buttons[chat_id] = {}
    pressed_buttons[chat_id][TipoOferta.DISPOSITIVO.value] = {}
    descripcionPedido[chat_id] = {}
    descripcionPedido[chat_id]["device_model"] = oferta.get("name") 

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('😊 Sí, ¡encantado!', callback_data=f"{TipoOferta.DISPOSITIVO.value},aceptar_oferta_dispositivo,ofr_yes")
    btn2 = types.InlineKeyboardButton('💭 No, quizá en otro momento', callback_data=f"{TipoOferta.DISPOSITIVO.value},aceptar_oferta_dispositivo,ofr_no")
    markup.add(btn1, btn2)

    bot.send_message(chat_id, f'Por tu reciente petición en {oferta.get("origin")}, ¡¡consigue un {oferta.get("name")} con un {oferta.get("discount")}% de descuento!!')
    bot.send_message(chat_id, '¿Te gustaría aprovechar esta oferta?', reply_markup=markup)

def send_plan_offer(oferta):
    chat_id = oferta.get("chat_id")

    pressed_buttons[chat_id] = {} 
    pressed_buttons[chat_id][TipoOferta.TARIFA.value] = {}
    descripcionPedido[chat_id] = {}
    
    # Modificado: Guardamos la clave pura ('plan') para poder buscar en la app.
    # Si la Cloud Function antigua no manda el target, usamos el name como mecanismo de seguridad.
    descripcionPedido[chat_id]["plan"] = oferta.get("plan", oferta.get("name"))

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('😊 Sí, ¡encantado!', callback_data=f"{TipoOferta.TARIFA.value},aceptar_oferta_tarifa,ofr_yes")
    btn2 = types.InlineKeyboardButton('💭 No, quizá en otro momento', callback_data=f"{TipoOferta.TARIFA.value},aceptar_oferta_tarifa,ofr_no")
    markup.add(btn1, btn2)

    bot.send_message(chat_id, f'Por tu reciente compra en {oferta.get("origin")}, ¡¡Tienes un {oferta.get("discount")}% de descuento en nuestro plan {oferta.get("name")}!!')
    bot.send_message(chat_id, '¿Te gustaría aprovechar esta oferta?', reply_markup=markup)

##############################################################################
####################### Arranque del listener Firebase #######################
##############################################################################

cred = credentials.Certificate(f"{script_dir}/keys/serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://bbdd-multicanalidad-default-rtdb.europe-west1.firebasedatabase.app/'
})

def subscription_event(event):
    if event.event_type in ["put", "patch"]:
        if event.path == "/":
            if event.data is None:
                return 
            for oferta_id, oferta_data in event.data.items():
                procesar_y_marcar_oferta(oferta_id, oferta_data)
        else:
            oferta_id = event.path.strip("/")
            oferta_data = event.data
            procesar_y_marcar_oferta(oferta_id, oferta_data)

def procesar_y_marcar_oferta(oferta_id, oferta_data):
    """
    Recibe una oferta del nodo 'ofertas'. La oferta NO se marca como procesada al
    enviarla, sino cuando el cliente termina la conversación (finalizar_oferta).
    Así, si el backend se reinicia a mitad de una conversación, al volver a
    arrancar el listener recoge las ofertas con processed = false y las reenvía.
    """
    if not oferta_data or not isinstance(oferta_data, dict):
        return

    if oferta_data.get("processed"):
        return

    # MEDIDA (rama medidas): T2a de la latencia omnicanal. Momento en que el listener
    # recibe la oferta desde la RTDB. Marca de tiempo Unix en ms (UTC).
    print(f"[MEDIDA] T2a_oferta_recibida ts_ms={time.time_ns() // 1_000_000} oferta={oferta_id}", flush=True)

    tipo = oferta_data.get("type")
    try:
        if tipo == "device":
            OfferValidator.validate_device_offer(oferta_data)
        elif tipo == "plan":
            OfferValidator.validate_plan_offer(oferta_data)
        else:
            raise ValueError(f"tipo de oferta desconocido: {tipo}")
    except (ValueError, TypeError) as e:
        print(f"[ERROR] Oferta {oferta_id} descartada. Motivo: {e}")
        return

    chat_id = oferta_data.get("chat_id")

    with lock_ofertas:
        pendientes = ofertas_pendientes.setdefault(chat_id, deque())

        # Evita duplicados si el listener vuelve a notificar la misma oferta
        if oferta_activa.get(chat_id) == oferta_id or any(oid == oferta_id for oid, _ in pendientes):
            return

        # Si el cliente ya está atendiendo otra oferta, esta espera su turno
        if chat_id in oferta_activa:
            pendientes.append((oferta_id, oferta_data))
            print(f"[INFO] Oferta {oferta_id} en espera: el chat {chat_id} tiene otra oferta en curso.")
            return

        oferta_activa[chat_id] = oferta_id

    enviar_oferta(oferta_id, oferta_data)

def enviar_oferta(oferta_id, oferta_data):
    if oferta_data.get("type") == "device":
        send_device_offer(oferta_data)
    else:
        send_plan_offer(oferta_data)
    # MEDIDA (rama medidas): T2b de la latencia omnicanal. Momento en que Telegram ha
    # aceptado el último mensaje de la oferta. Marca de tiempo Unix en ms (UTC).
    print(f"[MEDIDA] T2b_oferta_enviada_telegram ts_ms={time.time_ns() // 1_000_000} oferta={oferta_id}", flush=True)
    print(f"[INFO] Oferta {oferta_id} enviada a Telegram. Pendiente de respuesta del cliente.")

def finalizar_oferta(chat_id):
    """
    Se llama cuando el cliente rechaza la oferta al inicio, la cancela al final o
    la acepta. Marca la oferta como procesada, limpia el estado de la conversación
    y, si había más ofertas esperando para ese chat, envía la siguiente.
    """
    descripcionPedido.pop(chat_id, None)
    pressed_buttons.pop(chat_id, None)

    with lock_ofertas:
        oferta_id = oferta_activa.pop(chat_id, None)
        pendientes = ofertas_pendientes.get(chat_id)
        siguiente = pendientes.popleft() if pendientes else None
        if siguiente:
            oferta_activa[chat_id] = siguiente[0]

    if oferta_id:
        try:
            db.reference(f'ofertas/{oferta_id}').update({"processed": True})
            print(f"[INFO] Oferta {oferta_id} finalizada por el cliente y marcada como procesada.")
        except Exception as e:
            print(f"[ERROR] No se pudo marcar la oferta {oferta_id} como procesada: {e}")

    if siguiente:
        enviar_oferta(*siguiente)

#######################################################################################
################### Definición controladores de señales ###############################
#######################################################################################

APAGANDO = False
LISTENER_FB = {}

def stop_backend(signum, frame):
    global APAGANDO
    if APAGANDO: return
    APAGANDO = True
    
    print("Parada iniciada")
    print("Deteniendo bot de Telegram...")
    bot.stop_bot()

    print("Deteniendo Listener de Firebase...")
    try:
        LISTENER_FB.close()
    except:
        pass

    print("Finalizando programa...")
    sys.exit(0)

signal.signal(signal.SIGINT, stop_backend)
signal.signal(signal.SIGTERM, stop_backend) 

##############################################################################
####################### Arranque del servidor backend ########################
##############################################################################

def start_backend_telegram():
    try:
        print("Todo listo!. Pulsa CTRL + C para cerrar.")
        global LISTENER_FB
        LISTENER_FB = start_offer_service()
        bot.infinity_polling(skip_pending=True, timeout=10)
    except (KeyboardInterrupt, EOFError):
        pass

def start_offer_service():
    ref_mensajes = db.reference('ofertas')
    listener = ref_mensajes.listen(subscription_event)
    print("Escuchando nuevas ofertas en tiempo real...")
    return listener

if __name__ == "__main__":
    start_backend_telegram()
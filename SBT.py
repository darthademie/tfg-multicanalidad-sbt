# Dependencias de firebase
import firebase_admin
from firebase_admin import credentials, db

# Importamos Telegram
import telebot
from telebot import types

# Llamadas al sistema
import os
import sys
import signal

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

# Token de acceso del bot proporcionado por BotFather
TOKEN = None

ruta_token = os.path.join('keys', 'telegram_token.txt')

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

# Inicializa el bot con el token
bot = telebot.TeleBot(TOKEN)

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
    # Modificado: Se envían textos naturales en el callback_data
    btn1 = types.InlineKeyboardButton('🔓 Sin permanencia', callback_data=f"{TipoOferta.TARIFA.value},pedir_permanencia,perm1,Sin permanencia")
    btn2 = types.InlineKeyboardButton('🔒 12 Meses', callback_data=f"{TipoOferta.TARIFA.value},pedir_permanencia,perm2,12 meses")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "Para adaptar la tarifa a tus necesidades, necesitamos configurar el contrato.")
    bot.send_message(message.chat.id, "¿Prefieres libertad total sin ataduras, o comprometerte 12 meses a cambio de mantener estas condiciones ventajosas?", reply_markup=markup)

def ask_extras(message):
    markup = types.InlineKeyboardMarkup()
    # Modificado: Se envían textos naturales en el callback_data
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
            bot.send_message(chat_id, "¡Buena decisión! Comenzemos el proceso de envío")
            ask_rom(call.message)
        elif boton == "ofr_no":
            bot.send_message(chat_id, "¡Sin problema! Te mantendremos informado de las últimas ofertas que te puedan resultar interesantes 😉")
        elif (boton == "alm1") | (boton == "alm2"):
            descripcionPedido[chat_id]["storage"] = infoBoton
            bot.send_message(chat_id, "¡Estupendo!")
            ask_color(call.message)
        elif (boton == "color1") | (boton == "color2"):
            descripcionPedido[chat_id]["color"] = infoBoton
            bot.send_message(chat_id, "¡Genial! Buena elección 😉")
            ask_confirmation_device(call.message)
        elif (boton == "offer_confirm"):
            send_device_data(chat_id)
            del descripcionPedido[chat_id]
            del pressed_buttons[chat_id]
            bot.send_message(chat_id, "¡Perfecto! Tu pedido será enviado en breve a la dirección que proporcionaste a Tele UPM. Muchas gracias por confiar en nosotros 😄")
        elif (boton == "offer_no_confirm"):
            del descripcionPedido[chat_id]
            del pressed_buttons[chat_id]
            bot.send_message(chat_id, "¡Sin problema! Te mantendremos informado de las últimas ofertas relevantes 😄")
            
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
            bot.send_message(chat_id, "¡Buena decisión! Comenzemos el proceso de personalización de tu tarifa.")
            ask_permanencia(call.message)
        elif boton == "ofr_no":
            bot.send_message(chat_id, "¡Sin problema! Te mantendremos informado de las últimas ofertas que te puedan resultar interesantes 😉")
        elif (boton == "perm1") | (boton == "perm2"):
            descripcionPedido[chat_id]["permanencia"] = infoBoton
            bot.send_message(chat_id, "¡Anotado!")
            ask_extras(call.message)
        elif (boton == "ext1") | (boton == "ext2"):
            descripcionPedido[chat_id]["extras"] = infoBoton
            bot.send_message(chat_id, "¡Genial! Una buena decisión 😉")
            ask_confirmation_plan(call.message)
        elif (boton == "offer_confirm"):
            send_plan_data(chat_id)
            del descripcionPedido[chat_id]
            del pressed_buttons[chat_id]
            bot.send_message(chat_id, "¡Perfecto! Tu nueva tarifa ha sido procesada y se activará en tu línea en los próximos minutos. ¡A disfrutar! 🎉")
        elif (boton == "offer_no_confirm"):
            del descripcionPedido[chat_id]
            del pressed_buttons[chat_id]
            bot.send_message(chat_id, "Operación cancelada. Si cambias de opinión, ¡estaremos por aquí! 😄")

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
    
    ref_tarifas = db.reference('cola_procesamiento/tarifas')
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

    bot.send_message(chat_id, f'Por tu reciente subscripción a {oferta.get("origin")}, ¡¡consigue un {oferta.get("name")} con un {oferta.get("discount")}% de descuento!!')
    bot.send_message(chat_id, '¿Te gustaría aprovechar esta oferta?', reply_markup=markup)


def send_plan_offer(oferta):
    chat_id = oferta.get("chat_id")

    pressed_buttons[chat_id] = {} 
    pressed_buttons[chat_id][TipoOferta.TARIFA.value] = {}
    descripcionPedido[chat_id] = {}
    
    # Modificado: Guardamos la clave pura ('plan') en lugar del nombre bonito para poder buscar en la app.
    # Si la Cloud Function antigua no manda el target, usamos el name como mecanismo de seguridad.
    descripcionPedido[chat_id]["plan"] = oferta.get("plan", oferta.get("name"))

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('😊 Sí, ¡encantado!', callback_data=f"{TipoOferta.TARIFA.value},aceptar_oferta_tarifa,ofr_yes")
    btn2 = types.InlineKeyboardButton('💭 No, quizá en otro momento', callback_data=f"{TipoOferta.TARIFA.value},aceptar_oferta_tarifa,ofr_no")
    markup.add(btn1, btn2)

    bot.send_message(chat_id, f'Por tu reciente compra de un {oferta.get("origin")}, ¡¡Tienes un {oferta.get("discount")}% de descuento en nuestro plan {oferta.get("name")}!!')
    bot.send_message(chat_id, '¿Te gustaría aprovechar esta oferta?', reply_markup=markup)

##############################################################################
####################### Arranque del listener Firebase #######################
##############################################################################

script_dir = Path(__file__).parent

cred = credentials.Certificate(f"{script_dir}./keys/serviceAccountKey.json")
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
    if not oferta_data or not isinstance(oferta_data, dict):
        return
        
    if not oferta_data.get("processed"):
        try:
            tipo = oferta_data.get("type")
            if tipo == "device":
                OfferValidator.validate_device_offer(oferta_data)
                send_device_offer(oferta_data)
            elif tipo == "plan":
                if hasattr(OfferValidator, 'validate_plan_offer'):
                    OfferValidator.validate_plan_offer(oferta_data) 
                send_plan_offer(oferta_data)
                
            db.reference(f'ofertas/{oferta_id}').update({
                "processed": True
            })
            print(f"[INFO] Oferta {oferta_id} enviada a Telegram y marcada como procesada.")
            
        except (ValueError, TypeError) as e:
            print(f"[ERROR] Oferta {oferta_id} descartada. Motivo: {e}")

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
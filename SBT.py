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

################## Funciones

################## Incializacion thread de libreta jupyter

# Token de acceso del bot proporcionado por BotFather
TOKEN = None

# Ruta al archivo que contiene el token (ajusta si tu script principal está en otro nivel)
ruta_token = os.path.join('keys', 'telegram_token.txt')

try:
    with open(ruta_token, 'r') as archivo:
        # read().strip() lee el contenido y elimina espacios o saltos de línea al principio y al final
        TOKEN = archivo.read().strip()
        
    if not TOKEN:
        raise ValueError("El archivo del token está vacío.")
        
except FileNotFoundError:
    print(f"[ERROR] No se ha encontrado el archivo del token en {ruta_token}")
    print("Asegúrate de haber creado el archivo 'telegram_token.txt' dentro de la carpeta 'keys'.")
    exit(1)
except Exception as e:
    print(f"[ERROR] Error al leer el token: {e}")
    exit(1)

# Diccionario para rastrear qué botones se han presionado
# por chat_id
pressed_buttons = {}

# Inicializamos una lista que contenga los detalles del pedido
descripcionPedido = {}

# Inicializa el bot con el token
bot = telebot.TeleBot(TOKEN)

# Maneja el comando '/start'
@bot.message_handler(commands=['start'])
def start(message):
    # Envía el mensaje de bienvenida
    bot.send_message(message.chat.id, "¡Bienvenido! Has contactado con el bot de asistencia de TeleUPM 🤖, tu empresa favorita de telefonía y redes móviles")
    print(message.chat.id)

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

    bot.send_message(message.chat.id, "¿En qué color te gustaría obtener tu nuevo móvil?", reply_markup=markup)

def ask_confirmation(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('❌ Detener proceso', callback_data=f"{TipoOferta.DISPOSITIVO.value},confirmar_pedido,offer_no_confirm")
    btn2 = types.InlineKeyboardButton('✔ Aceptar y enviar', callback_data=f"{TipoOferta.DISPOSITIVO.value},confirmar_pedido,offer_confirm")
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id, "¿Es todo correcto? Si es así, dará comienzo el proceso de envío 😄", reply_markup=markup)

# Maneja los mensajes de callback de ofertas sobre dispositivos
@bot.callback_query_handler(func=lambda call: call.data.split(',')[0] == TipoOferta.DISPOSITIVO.value)
def callback_query(call):

    # Recogemos el id del chat
    chat_id = call.message.chat.id
    
    if call.data and pressed_buttons.get(chat_id, False):

        # Extraemos en forma de lista los parámetros pasados al callback
        parametros = call.data.split(',')

        # Extraemos el grupo en el que se encuentran los botones del mensaje actual
        # parametros[0] contiene la información sobre el tipo de oferta
        grupoBotones = parametros[1]

        # Extraemos la información relacionada con el botón que se ha pulsado
        boton = parametros[2]

        # Si tenemos la información asociada al botón como parámetro, la recogemos en infoBoton
        if len(parametros) == 4:
            infoBoton = parametros[3]

        # Verifica si el botón ya ha sido presionado
        if grupoBotones in pressed_buttons[chat_id][TipoOferta.DISPOSITIVO.value] and pressed_buttons[chat_id][TipoOferta.DISPOSITIVO.value][grupoBotones] == True:
            bot.answer_callback_query(call.id, text="Ya has seleccionado una opción.")
            return

        # En caso contrario, miramos qué botón es el que se ha pulsado y mandamos el siguiente mensaje en consecuencia
        if boton == "ofr_yes":
            msg = bot.send_message(chat_id, "¡Buena decisión! Comenzemos el proceso de envío")
            bot.register_next_step_handler(msg, ask_rom(call.message))
        elif boton == "ofr_no":
            bot.send_message(chat_id, "¡Sin problema! Te mantendremos informado de las últimas ofertas que te puedan resultar interesantes 😉")
        elif (boton == "alm1") | (boton == "alm2"):
            descripcionPedido[chat_id]["storage"] = infoBoton
            msg = bot.send_message(chat_id, "¡Estupendo!")
            bot.register_next_step_handler(msg, ask_color(call.message))
        elif (boton == "color1") | (boton == "color2"):
            descripcionPedido[chat_id]["color"] = infoBoton
            msg = bot.send_message(chat_id, "¡Genial! Buena elección 😉")
            bot.register_next_step_handler(msg, ask_confirmation(call.message))
        elif (boton == "offer_confirm"):
            # Manda el pedido confirmado a Firebase RTDB
            # Considerar uso de cloud functions y una estructura desligada de la que
            # Pillan la web de Tele UPM y la app de envíos 43
            send_device_data(chat_id)
            # Borramos los datos de envío
            del descripcionPedido[chat_id]
            # Marcamos como presionado el botón actual
            del pressed_buttons[chat_id]
            bot.send_message(chat_id, "¡Perfecto! tu pedido será enviado en breve a la dirección que proporcionaste a Tele UPM. Muchas gracias por confiar en nosotros 😄")
        elif (boton == "offer_no_confirm"):
            # Borramos los datos de envío
            del descripcionPedido[chat_id]
            # Marcamos como presionado el botón actual
            del pressed_buttons[chat_id]
            bot.send_message(chat_id, "¡Sin problema! Te mantendremos informado de las últimas ofertas relevantes 😄")
            

        if ( grupoBotones != "confirmar_pedido" ):
            # Marcamos como presionado el botón actual
            pressed_buttons[chat_id][TipoOferta.DISPOSITIVO.value][grupoBotones] = True

def send_device_data(chat_id):
    datos_pedido = {
        "user_id": chat_id,
        "type": "telegram",
        "order_type": "device",
        "device_model": descripcionPedido[chat_id]["device_model"],
        "storage": descripcionPedido[chat_id]["storage"],
        "color": descripcionPedido[chat_id]["color"],
        "fecha": {".sv": "timestamp"} # Variable especial de Firebase para guardar la hora exacta del servidor
    }
    
    # 2. Apuntamos al nodo raíz donde se guardarán los pedidos (lo crea si no existe)
    ref_pedidos = db.reference('cola_procesamiento/pedidos')

    print(datos_pedido)
    
    # Usamos push() para que Firebase genere una clave alfanumérica única para este pedido concreto
    ref_pedidos.push(datos_pedido)

# Maneja los mensajes de callback de ofertas sobre tarifas
@bot.callback_query_handler(func=lambda call: call.data.split(',')[0] == TipoOferta.TARIFA.value)
def callback_query(call):
    if call.data:
        # Recogemos el id del chat
        chat_id = call.message.chat.id
        # Extraemos en forma de lista los parámetros pasados al callback
        parametros = call.data.split(',')

        # Extraemos el grupo en el que se encuentran los botones del mensaje actual
        # parametros[0] contiene la información sobre el tipo de oferta
        grupoBotones = parametros[1]

        # Extraemos la información relacionada con el botón que se ha pulsado
        boton = parametros[2]

        # Si tenemos la información asociada al botón como parámetro, la recogemos en infoBoton
        if len(parametros) == 4:
            infoBoton = parametros[3]

        # Verifica si el botón ya ha sido presionado
        if grupoBotones in pressed_buttons[chat_id][TipoOferta.TARIFA.value] and pressed_buttons[chat_id][TipoOferta.TARIFA.value][grupoBotones] == True:
            bot.answer_callback_query(call.id, text="Ya has seleccionado una opción.")
            return

        # En caso contrario, miramos qué botón es el que se ha pulsado y mandamos el siguiente mensaje en consecuencia
        if boton == "ofr_yes":
            msg = bot.send_message(chat_id, "¡Buena decisión! Comenzemos el proceso de personalización de tu oferta")
        elif boton == "ofr_no":
            bot.send_message(chat_id, "¡Sin problema! Te mantendremos informado de las últimas ofertas que te puedan resultar interesantes 😉")
        elif (boton == "alm1") | (boton == "alm2"):
            descripcionPedido[chat_id].append(infoBoton)
            msg = bot.send_message(chat_id, "¡Estupendo!")
            bot.register_next_step_handler(msg, ask_color(call.message))
        elif (boton == "color1") | (boton == "color2"):
            descripcionPedido[chat_id].append(infoBoton)
            msg = bot.send_message(chat_id, "¡Genial! Una buena decisión 😉")
            bot.register_next_step_handler(msg, ask_confirmation(call.message))

        # Marcamos como presionado el botón actual
        pressed_buttons[chat_id][TipoOferta.TARIFA.value][grupoBotones] = True

##############################################################################
####################### Definición de funciones de API #######################
##############################################################################

# Función para enviar un mensaje automáticamente a un usuario
def send_device_offer(oferta):

    chat_id = oferta.get("chat_id")

    # Variables comunes al usuario actual
    pressed_buttons[chat_id] = {} # Inicializamos un diccionario de botones presionados por usuario, con su ID
    pressed_buttons[chat_id][TipoOferta.DISPOSITIVO.value] = {}
    descripcionPedido[chat_id] = {}
    descripcionPedido[chat_id]["device_model"] = oferta.get("name") # Añadimos como primer dato el nombre del dispositivo indicado por la oferta

    # Crea los botones de reacción
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('😊 Sí, ¡encantado!', callback_data=f"{TipoOferta.DISPOSITIVO.value},aceptar_oferta_dispositivo,ofr_yes")
    btn2 = types.InlineKeyboardButton('💭 No, quizá en otro momento', callback_data=f"{TipoOferta.DISPOSITIVO.value},aceptar_oferta_dispositivo,ofr_no")
    markup.add(btn1, btn2)

    # Informa de la oferta
    bot.send_message(chat_id, f'Por tu reciente subscripción a {oferta.get("origin")}, ¡¡consigue un {oferta.get("name")} con un {oferta.get("discount")}% de descuento!!')
    # Envía los botones de reacción debajo del mensaje anterior
    bot.send_message(chat_id, '¿Te gustaría aprovechar esta oferta?', reply_markup=markup)

# Envío de tarifas
def send_plan_offer(oferta):

    chat_id = oferta.get("chat_id")

    # Variables comunes al usuario actual
    pressed_buttons[chat_id] = {} # Inicializamos un diccionario de botones presionados por usuario, con su ID
    pressed_buttons[chat_id][TipoOferta.TARIFA.value] = {}
    descripcionPedido = {} # Generamos un diccionario nuevo para los detalles del posible pedido
    descripcionPedido[chat_id] = {}
    descripcionPedido[chat_id]["device_model"] = oferta.get("name") # Añadimos como primer dato el nombre del dispositivo indicado por la oferta


    # Crea los botones de reacción
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('😊 Sí, ¡encantado!', callback_data=f"{TipoOferta.TARIFA.value},aceptar_oferta_tarifa,ofr_yes")
    btn2 = types.InlineKeyboardButton('💭 No, quizá en otro momento', callback_data=f"{TipoOferta.TARIFA.value},aceptar_oferta_tarifa,ofr_no")
    markup.add(btn1, btn2)

    # Informa de la oferta
    bot.send_message(chat_id, f'Por tu reciente compra de un {oferta.get("origin")}, ¡¡Tienes un {oferta.get("discount")}% de descuento en nuestro plan {oferta.get("name")}!!')
    # Envía los botones de reacción debajo del mensaje anterior
    bot.send_message(chat_id, '¿Te gustaría aprovechar esta oferta?', reply_markup=markup)

##############################################################################
####################### Arranque del listener Firebase #######################
##############################################################################

# Obtiene la ruta absoluta de la carpeta donde está este script
script_dir = Path(__file__).parent

# 1. Configuración inicial (igual que siempre)
cred = credentials.Certificate(f"{script_dir}./keys/serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://bbdd-multicanalidad-default-rtdb.europe-west1.firebasedatabase.app/'
})

# 2. Definimos la función "Callback" (la que reacciona)
def subscription_event(event):
    if event.event_type in ["put", "patch"]:
        print(f"Tipo de evento: {event.event_type} | Ruta: {event.path}")

        # CASO A: Se lee el nodo completo (ocurre al iniciar el script)
        if event.path == "/":
            if event.data is None:
                return # El nodo está vacío
            
            # Iteramos sobre el diccionario de ofertas { "id1": {...}, "id2": {...} }
            for oferta_id, oferta_data in event.data.items():
                procesar_y_marcar_oferta(oferta_id, oferta_data)
                
        # CASO B: Entra una oferta individual nueva mediante push()
        else:
            # event.path trae la barra inicial (ej: "/-Nabc123"), la limpiamos para sacar el ID
            oferta_id = event.path.strip("/")
            oferta_data = event.data
            procesar_y_marcar_oferta(oferta_id, oferta_data)


def procesar_y_marcar_oferta(oferta_id, oferta_data):
    # Evitamos fallos si se ha borrado la oferta o el formato es incorrecto
    if not oferta_data or not isinstance(oferta_data, dict):
        return
        
    if not oferta_data.get("processed"):
        try:
            tipo = oferta_data.get("type")
            if tipo == "device":
                OfferValidator.validate_device_offer(oferta_data)
                send_device_offer(oferta_data)
            elif tipo == "plan":
                # OJO: En tu código tenías puesto validate_device_offer aquí también. 
                # Cámbialo a validate_plan_offer si tienes ese método creado en tu clase OfferValidator.
                OfferValidator.validate_device_offer(oferta_data) 
                send_plan_offer(oferta_data)
                
            # MARCAR COMO PROCESADA EN FIREBASE
            # Apuntamos exactamente al ID de la oferta para no sobreescribir el nodo raíz
            db.reference(f'ofertas/{oferta_id}').update({
                "processed": True
            })
            print(f"[INFO] Oferta {oferta_id} enviada a Telegram y marcada como procesada.")
            
        except (ValueError, TypeError) as e:
            print(f"[ERROR] Oferta {oferta_id} descartada. Motivo: {e}")

#######################################################################################
################### Definición controladores de señales ###############################
#######################################################################################

# Variable global para evitar spam de CTRL+C
APAGANDO = False
LISTENER_FB = {}

def stop_backend(signum, frame):
    global APAGANDO
    if APAGANDO: return
    APAGANDO = True
    
    print("Parada iniciada")

    # 2. Detener bot de telegram
    print("Deteniendo bot de Telegram...")
    bot.stop_bot()

    # 3. CERRAR FIREBASE
    print("Deteniendo Listener de Firebase...")
    try:
        LISTENER_FB.close()
    except:
        pass

    print("Finalizando programa...")
    sys.exit(0)

# --- VINCULAMOS LA SEÑAL ---
# Esto le dice a Python: "Cuando recibas SIGINT (Ctrl+C), NO lances KeyboardInterrupt.
# En su lugar, ejecuta mi función 'gestor_parada'".
signal.signal(signal.SIGINT, stop_backend)
signal.signal(signal.SIGTERM, stop_backend) # Para Docker/Servidores

##############################################################################
####################### Arranque del servidor backend ########################
##############################################################################

def start_backend_telegram():
    try:
        # Iniciar bot telegram
        print("Todo listo!. Pulsa CTRL + C para cerrar.")
        global LISTENER_FB
        LISTENER_FB = start_offer_service()
        bot.infinity_polling(skip_pending=True, timeout=10)
    except (KeyboardInterrupt, EOFError):
        pass

def start_offer_service():
    # Referencia al nodo que queremos vigilar
    ref_mensajes = db.reference('ofertas')

    # Activar la escucha
    listener = ref_mensajes.listen(subscription_event)

    print("Escuchando nuevas ofertas en tiempo real...")

    return listener

# Lanzar servicio completo
if __name__ == "__main__":
    start_backend_telegram()

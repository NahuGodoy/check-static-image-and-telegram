import pyaudio
import numpy as np
import time
import asyncio
import cv2
from PIL import Image, ImageChops
import telegram
import io
import credentials as cred
import paho.mqtt.publish as publish
import argparse

#Modificable con argumentos
tiempo_de_espera = 5  # Tiempo de espera para comprobar si la imagen estática permanece en segundos
THRESHOLD = 0.7  # Umbral de energía para considerar que hay audio
SILENCE_TIMEOUT = 5  # Tiempo en segundos para considerar que no hay audio

# Función para procesar los argumentos
def procesar_argumentos():
    global tiempo_de_espera, THRESHOLD, SILENCE_TIMEOUT

    parser = argparse.ArgumentParser(description='Tiempo y umbral')

    # Agregar argumentos con valores predeterminados
    parser.add_argument('-tempi', '--tempImage', type=int, default=30, help='Tiempo de espera para comprobar si la imagen estática permanece en segundos')
    parser.add_argument('-tempa', '--tempAudio', type=int, default=30, help='Tiempo que hasta dar aviso que no hay audio en segundos')
    parser.add_argument('-umba', '--umbralAudio', type=float, default=0.7, help='Umbral del ruido blanco')


    args = parser.parse_args()

    # Modificar las variables según los argumentos recibidos
    tiempo_de_espera = args.tempImage
    SILENCE_TIMEOUT = args.tempAudio
    THRESHOLD = args.umbralAudio

    print(tiempo_de_espera, SILENCE_TIMEOUT, THRESHOLD)


# Llamar a la función para procesar los argumentos
procesar_argumentos()

#MQTT Configuración
mqtt_host = cred.mqtt_host
mqtt_port = cred.mqtt_port
mqtt_user = cred.mqtt_user
mqtt_pass = cred.mqtt_pass

# Configuración de audio
RATE = 44100
CHUNK = 1024

# Configuración de Telegram
TOKEN = cred.TOKEN
CHAT_ID = cred.CHAT_ID

# Función para comparar imágenes
def images_are_equal(img1, img2):
    diff = ImageChops.difference(img1, img2)
    return diff.getbbox() is None

# Función para enviar un mensaje por Telegram
async def send_telegram_message(message):
    bot = telegram.Bot(token=TOKEN)
    await bot.sendMessage(chat_id=CHAT_ID, text=message)

# Función para enviar un mensaje con imagen por Telegram
async def send_telegram_message_with_image(message, image):
    bot = telegram.Bot(token=TOKEN)
    with image as img:
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        await bot.send_photo(chat_id=CHAT_ID, photo=bio, caption=message)

# Función para capturar un fotograma desde la cámara virtual
def capture_frame():
    cap = cv2.VideoCapture(2)  # 0 para la primera cámara, 1 para la segunda, etc.
    ret, frame = cap.read()
    cap.release()
    return frame

# Función para verificar si la imagen ha estado estática durante un cierto tiempo
def check_static_image(timeout):
    previous_image = Image.fromarray(cv2.cvtColor(capture_frame(), cv2.COLOR_BGR2RGB))
    time.sleep(timeout)
    current_image = Image.fromarray(cv2.cvtColor(capture_frame(), cv2.COLOR_BGR2RGB))
    if images_are_equal(previous_image, current_image):
        return True
    previous_image = current_image

# Función para verificar si hay audio presente
def is_audio_present(data):
    try:
        abs_data = np.abs(np.mean(np.square(data)))
        rms = np.sqrt(abs_data)
        return rms > THRESHOLD
    except Exception as e:
        print("Error while calculating audio energy:", e)
        return True

# Función principal
async def main():
    print("Iniciando el programa de detección de imágenes estáticas y audio...")
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1,
                        rate=RATE, input=True,
                        frames_per_buffer=CHUNK)

    silence_timer = time.time()
    audio_alert_sent = False

    try:
        while True:
            # Comprobación de audio
            data = np.frombuffer(stream.read(CHUNK), dtype=np.int16)
            if is_audio_present(data):
                silence_timer = time.time()
                audio_alert_sent = False
            elif time.time() - silence_timer > SILENCE_TIMEOUT:
                print("No audio detected for", SILENCE_TIMEOUT, "seconds.")
                if not audio_alert_sent:
                    # Enviar alerta por Telegram
                    print("Sending audio alert via Telegram...")
                    await send_telegram_message("¡Alerta! No se detecta audio desde hace 5 segundos.")
                    audio_alert_sent = True
            # Continuar con la verificación de la imagen estática
            if check_static_image(tiempo_de_espera):
                print("¡Alerta! La imagen en pantalla se ha mantenido estática durante mucho tiempo.")
                # Captura el fotograma actual
                current_frame = capture_frame()
                # Convierte el fotograma en una imagen
                current_image = Image.fromarray(cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB))
                # Envía un mensaje por Telegram con la imagen
                await send_telegram_message_with_image("¡Alerta! La imagen en pantalla se ha mantenido estática durante mucho tiempo.", current_image)
                #MQTT imagen
                publish.single("vmix/imagen", payload="Congelado", hostname=mqtt_host, port=mqtt_port, auth={'username': mqtt_user, 'password': mqtt_pass})
            else:
                print("¡Alerta! Imagenes distintas")
                # Captura el fotograma actual
                current_frame = capture_frame()
                # Convierte el fotograma en una imagen
                current_image = Image.fromarray(cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB))
                # Envía un mensaje por Telegram con la imagen
                await send_telegram_message_with_image("Imagenes distintas", current_image)
                publish.single("vmix/imagen", payload="Normal", hostname=mqtt_host, port=mqtt_port, auth={'username': mqtt_user, 'password': mqtt_pass})
            #MQTT
            if(audio_alert_sent):
                publish.single("vmix/audio", payload="Congelado", hostname=mqtt_host, port=mqtt_port, auth={'username': mqtt_user, 'password': mqtt_pass})
            else:
                publish.single("vmix/audio", payload="Normal", hostname=mqtt_host, port=mqtt_port, auth={'username': mqtt_user, 'password': mqtt_pass})
    except KeyboardInterrupt:
        print("\nPrograma detenido por el usuario.")
        stream.stop_stream()
        stream.close()
        audio.terminate()

if __name__ == "__main__":
    asyncio.run(main())

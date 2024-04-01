import asyncio
import time
import cv2
from PIL import Image, ImageChops
import telegram
import io
import credentials as cred

# Configuración de Telegram
TOKEN = cred.TOKEN
CHAT_ID = cred.CHAT_ID

# Función para comparar imágenes
def images_are_equal(img1, img2):
    diff = ImageChops.difference(img1, img2)
    return diff.getbbox() is None

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
    cap = cv2.VideoCapture(1)  # 0 para la primera cámara, 1 para la segunda, etc.
    ret, frame = cap.read()
    cap.release()
    return frame

# Función para verificar si la imagen ha estado estática durante un cierto tiempo
def check_static_image(timeout):
    previous_image = Image.fromarray(cv2.cvtColor(capture_frame(), cv2.COLOR_BGR2RGB))
    time.sleep(timeout)
    print("Comparando")
    current_image = Image.fromarray(cv2.cvtColor(capture_frame(), cv2.COLOR_BGR2RGB))
    if images_are_equal(previous_image, current_image):
        print("son iguales")
        return True
    previous_image = current_image

# Función principal
async def main():
    # Tiempo de espera para comprobar si la imagen estática permanece
    tiempo_de_espera = 5  # segundos

    print("Iniciando el programa de detección de imágenes estáticas...")
    try:
        while True:
            if check_static_image(tiempo_de_espera):
                print("¡Alerta! La imagen en pantalla se ha mantenido estática durante mucho tiempo.")
                # Captura el fotograma actual
                current_frame = capture_frame()
                # Convierte el fotograma en una imagen
                current_image = Image.fromarray(cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB))
                # Envía un mensaje por Telegram con la imagen
                await send_telegram_message_with_image("¡Alerta! La imagen en pantalla se ha mantenido estática durante mucho tiempo.", current_image)
            else:
                # Captura el fotograma actual
                current_frame = capture_frame()
                # Convierte el fotograma en una imagen
                current_image = Image.fromarray(cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB))
                await send_telegram_message_with_image("Son distintas.", current_image)
    except KeyboardInterrupt:
        print("\nPrograma detenido por el usuario.")

if __name__ == "__main__":
    asyncio.run(main())

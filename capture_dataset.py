import cv2
import os

# Buat folder untuk menyimpan foto jika belum ada
output_dir = "dataset_esp32"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Ganti dengan IP ESP32-CAM Anda
ESP32_URL = "http://192.168.18.27:81/stream" 
cap = cv2.VideoCapture(ESP32_URL)

img_count = 0
print("Kamera ESP32-CAM siap!")
print("Tekan 's' untuk memotret (Save). Tekan 'q' untuk keluar.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Koneksi terputus!")
        break

    cv2.imshow("Capture Dataset ESP32", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('s'):
        # Simpan gambar saat tombol 's' ditekan
        img_name = os.path.join(output_dir, f"esp32_billet_{img_count}.jpg")
        cv2.imwrite(img_name, frame)
        print(f"📸 Foto disimpan: {img_name}")
        img_count += 1
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
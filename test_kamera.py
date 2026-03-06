import cv2

# Masukkan URL Stream ESP32-CAM Anda yang berhasil dibuka di browser tadi
stream_url = "http://billet.local:81/stream"

print("Mencoba terhubung ke kamera ESP32...")
cap = cv2.VideoCapture(stream_url)

if not cap.isOpened():
    print("Error: Tidak bisa membuka stream video. Cek kembali IP Address atau koneksi WiFi.")
    exit()

print("Kamera berhasil terhubung! Tekan huruf 'q' di keyboard untuk keluar.")

while True:
    # Membaca frame video satu per satu
    ret, frame = cap.read()
    
    if not ret:
        print("Gagal menerima frame video")
        break

    # Menampilkan video di jendela baru
    cv2.imshow("Kamera ESP32-CAM", frame)

    # Logika untuk keluar dari program jika tombol 'q' ditekan
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Membersihkan memori setelah selesai
cap.release()
cv2.destroyAllWindows()
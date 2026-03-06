import cv2
import supervision as sv
from inference import get_model

MODEL_ID = "billet-detection-5znfl/2"
API_KEY  = "aWLCG4AiKBek0ujLpfPc`"

# ─── Threshold (sesuaikan dengan nilai di Roboflow UI) ───────────────────────
# Roboflow Confidence Threshold  : 0–100 di UI  → 0.0–1.0 di sini
# Roboflow Overlap Threshold     : 0–100 di UI  → 0.0–1.0 di sini
CONFIDENCE_THRESHOLD = 0.97   # 97%  – samakan dengan slider "Confidence Threshold"
OVERLAP_THRESHOLD    = 0.78   # 78%  – samakan dengan slider "Overlap Threshold"
# ─────────────────────────────────────────────────────────────────────────────

print("Memuat model dari Roboflow...")
model = get_model(model_id=MODEL_ID, api_key=API_KEY)
print("Model siap!")

# URL Stream ESP32-CAM
stream_url = "http://billet.local:81/stream"
print("Mencoba terhubung ke kamera ESP32...")
cap = cv2.VideoCapture(stream_url)

if not cap.isOpened():
    print("Error: Tidak bisa membuka stream video.")
    exit()

print(f"Kamera terhubung! AI berjalan "
      f"(confidence={CONFIDENCE_THRESHOLD}, overlap={OVERLAP_THRESHOLD}). "
      f"Tekan 'q' untuk keluar.")

box_annotator   = sv.BoxAnnotator()
label_annotator = sv.LabelAnnotator()

while True:
    ret, frame = cap.read()
    if not ret:
        print("Gagal menerima frame video")
        break

    frame = cv2.flip(frame, -1)

    # confidence  → Confidence Threshold di Roboflow UI (0.0–1.0)
    # iou_threshold → Overlap Threshold di Roboflow UI (0.0–1.0)
    results    = model.infer(frame,
                             confidence=CONFIDENCE_THRESHOLD,
                             iou_threshold=OVERLAP_THRESHOLD)[0]
    detections = sv.Detections.from_inference(results)

    labels = [f"{cn} {cf:.2f}"
              for cn, cf in zip(detections.data["class_name"], detections.confidence)]

    gambar_hasil = box_annotator.annotate(scene=frame.copy(), detections=detections)
    gambar_hasil = label_annotator.annotate(scene=gambar_hasil, detections=detections,
                                            labels=labels)

    cv2.imshow("Billet Detection - YOLO Lokal", gambar_hasil)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
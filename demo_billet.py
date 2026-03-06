import cv2
import numpy as np
from inference import get_model
import supervision as sv

# --- PENGATURAN MODEL ---
ROBOFLOW_API_KEY = "aWLCG4AiKBek0ujLpfPc"
MODEL_ID = "withs-workspace/billet-detection-5znfl-instant-1"

print("Sedang mengunduh otak AI dari Roboflow... (Mohon tunggu)")
model = get_model(model_id=MODEL_ID, api_key=ROBOFLOW_API_KEY)

# --- PENGATURAN KAMERA ---
print("Menghubungkan ke aliran video ESP32-CAM...")
ESP32_URL = "" 
cap = cv2.VideoCapture(ESP32_URL)

tracker = sv.ByteTrack()
box_annotator = sv.BoxAnnotator()
label_annotator = sv.LabelAnnotator()

# --- ⚙️ PENGATURAN FILTER WARNA METALIK ---
# Naikkan ke 120 untuk mentolerir pantulan lampu ruangan / bayangan
MAX_SATURATION = 120 

while True:
    ret, frame = cap.read()
    if not ret:
        print("Koneksi terputus! Cek jaringan Wi-Fi ESP32-CAM Anda.")
        break

    # AI menebak dengan syarat yakin minimal 50%
    results = model.infer(frame, confidence=0.5, iou_threshold=0.4)[0]
    detections = sv.Detections.from_inference(results)
    
    # 1. BIARKAN TRACKER BEKERJA DULU (Agar kotak stabil & tidak melompat)
    detections = tracker.update_with_detections(detections)
    
    # ====================================================
    # 2. HYBRID INTELLIGENCE: FILTER WARNA UNTUK RENDER
    # ====================================================
    valid_indices = []
    
    for i, xyxy in enumerate(detections.xyxy):
        class_name = detections.data['class_name'][i]
        
        if class_name == "billet":
            x1, y1, x2, y2 = map(int, xyxy)
            h_frame, w_frame = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_frame, x2), min(h_frame, y2)
            
            roi = frame[y1:y2, x1:x2]
            
            if roi.size > 0:
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                avg_saturation = hsv_roi[:, :, 1].mean()
                
                # Jika rata-rata saturasi di bawah 120 (Metalik / Abu-abu)
                if avg_saturation < MAX_SATURATION:
                    valid_indices.append(i)
        else:
            # Otomatis loloskan jika itu adalah 'baret' atau 'oksidasi'
            valid_indices.append(i)
            
    # Buang deteksi yang warnanya terlalu ngejreng
    detections = detections[valid_indices]
    # ====================================================

    # Siapkan label tulisan
    labels = []
    if len(detections) > 0:
        labels = [
            f"{class_name} {confidence:.2f}"
            for class_name, confidence
            in zip(detections.data['class_name'], detections.confidence)
        ]

    # Gambar kotak dan tulisan ke layar
    annotated_frame = box_annotator.annotate(scene=frame, detections=detections)
    
    if len(labels) > 0:
        annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=detections, labels=labels)

    cv2.imshow("Live Demo: Deteksi Cacat Billet", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
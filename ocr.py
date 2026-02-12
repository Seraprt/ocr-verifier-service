import io, hashlib
import numpy as np
import cv2
from PIL import Image, ExifTags
import easyocr 

reader = easyocr.Reader(["en"], gpu=False)

def load_image_bytes(upload_file):
  data = upload_file.file.read()
  image = Image.open(io.BytesIO(data)).convert("RGB")
  # Try EXIF timestamp
  exif_time = None
  try:
    exif = image._getexif()
    if exif:
      # Common EXIF DateTime tag
      for k, v in exif.items():
        tag = ExifTags.TAGS.get(k, k)
        if tag == "DateTimeOriginal" or tag == "DateTime":
          exif_time = str(v).replace(" ", "T").replace(":", "-", 2)  # YYYY:MM:DD HH:MM:SS -> YYYY-MM-DDTHH:MM:SS
          break
  except Exception:
    pass
  return np.array(image), data, exif_time

def bytes_hash(data: bytes):
  return hashlib.sha256(data).hexdigest()

def crop_roi(img, roi):
  h, w = img.shape[:2]
  x0 = int(roi[0] * w); y0 = int(roi[1] * h)
  x1 = int(roi[2] * w); y1 = int(roi[3] * h)
  return img[y0:y1, x0:x1]

def ocr_text(img):
  gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
  gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
  result = reader.readtext(gray, detail=0, paragraph=True)
  return " ".join(result).strip()

def parse_penalties(text: str):
  # Expect formats like "PK: 9 - 8" or "Penalties: 5-4"
  import re
  m = re.search(r"(\d+)\s*[-:\u2013]\s*(\d+)", text)
  if not m: return None, None
  return int(m.group(1)), int(m.group(2))

def parse_clock(text: str):
  # e.g., "54:34" or "67:24"
  import re
  m = re.search(r"(\d{1,3}):(\d{2})", text)
  if not m: return None
  minutes = int(m.group(1)); seconds = int(m.group(2))
  return minutes * 60 + seconds

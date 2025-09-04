import os
import sys

# --- Minimal .env loader (no external deps) ---
def load_dotenv(dotenv_path=".env"):
    if not os.path.exists(dotenv_path):
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Do not expand {VAR} placeholders; keep as-is
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        print(f"Warning: failed to load .env: {e}", file=sys.stderr)

# Attempt to load .env from CWD (project root where this file is located)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Ensure DJANGO_SETTINGS_MODULE is set (fallback to your .env default)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.base")

# --- Initialize Django BEFORE importing models/settings ---
import django
try:
    django.setup()
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

# Now it is safe to import Django settings and models
from django.conf import settings
from apps.multiparser.models import Product

# Optional: Tika import with graceful fallback
try:
    from tika import parser as tika_parser  # type: ignore
    TIKA_AVAILABLE = True
except Exception as _tika_err:
    tika_parser = None  # type: ignore
    TIKA_AVAILABLE = False

# ----- BOSHLANDI -----
PRODUCT_ID_TO_TEST = 391575

def safe_abs_path(media_root, file_path_from_db):
    # If file_path_from_db is absolute, return as-is; otherwise join with MEDIA_ROOT
    if os.path.isabs(file_path_from_db):
        return file_path_from_db
    return os.path.join(media_root, file_path_from_db)

def extract_text_with_tika(abs_file_path):
    if not TIKA_AVAILABLE:
        print("\nℹ️ Tika kutubxonasi mavjud emas. Matnni ajratib olish bosqichi o'tkazib yuborildi.")
        return None
    try:
        parsed_data = tika_parser.from_file(abs_file_path)  # type: ignore[attr-defined]
        return parsed_data.get('content') if parsed_data else None
    except Exception as e:
        print(f"\n❌❌❌ XATOLIK: Tika faylni o'qishda xatolikka uchradi: {e}")
        return None

try:
    print(f"STEP 1: Mahsulot (ID: {PRODUCT_ID_TO_TEST}) bazadan qidirilmoqda...")
    product = Product.objects.select_related('document').get(id=PRODUCT_ID_TO_TEST)
    print("✅ Mahsulot topildi:", getattr(product, "title", str(product)))

    document = getattr(product, "document", None)
    if not document:
        print("❌ XATOLIK: Mahsulotga bog'langan hujjat topilmadi.")
    else:
        print(f"STEP 2: Unga bog'langan hujjat (ID: {getattr(document, 'id', '—')}) tekshirilmoqda...")

        if not getattr(document, "file_path", None):
            print("❌ XATOLIK: Hujjatning serverdagi manzili ('file_path') topilmadi. Fayl yuklanmagan bo'lishi mumkin.")
        else:
            file_path_from_db = document.file_path
            print(f"✅ Hujjat manzili: {file_path_from_db}")

            media_root = getattr(settings, "MEDIA_ROOT", "")
            if not media_root:
                print("❌ XATOLIK: settings.MEDIA_ROOT sozlanmagan. Iltimos, Django sozlamalarini tekshiring.")
            abs_file_path = safe_abs_path(media_root, file_path_from_db)
            print(f"STEP 3: Faylning jismoniy mavjudligi tekshirilmoqda: {abs_file_path}")

            if not os.path.exists(abs_file_path):
                print(f"❌ XATOLIK: Fayl shu manzilda jismonan topilmadi!")
            else:
                print("✅ Fayl serverda mavjud.")
                print("STEP 4: Fayl ichidagi matnni o'qish boshlandi (agar Tika mavjud bo'lsa)...")

                content = extract_text_with_tika(abs_file_path)

                if content and content.strip():
                    print("\n✅ Fayl ichidagi matn muvaffaqiyatli o'qildi!")
                    if "мухторияти" in content.lower():
                        print("\n✅✅✅ TASDIQLANDI:  мухторияти so'zi o'qilgan matnda mavjud!")
                        print("--- Matndan parcha ---")
                        start_index = max(content.lower().find('мухторияти') - 50, 0)
                        print("..." + content[start_index: start_index + 100] + "...")
                    else:
                        print("\n❌❌❌ MUAMMONING ILDIZI: 'мухторияти' so'zi o'qilgan matnda TOPILMADI.")
                        print("--- Matnning birinchi 500 ta belgisi ---")
                        print(content.strip()[:500])
                else:
                    if TIKA_AVAILABLE:
                        print("\n❌❌❌ MUAMMONING ILDIZI: Matn ajratib olinmadi (bo'sh yoki o'qib bo'lmadi).")
                    else:
                        print("\nℹ️ Tika o'rnatilmagani sababli matn ajratib olinmadi. Tika qo'shilsa, matn o'qish imkoniyati paydo bo'ladi.")

except Product.DoesNotExist:
    print(f"❌ XATOLIK: ID si {PRODUCT_ID_TO_TEST} bo'lgan mahsulot bazada topilmadi.")
except Exception as e:
    print(f"❌ Kutilmagan xatolik yuz berdi: {e}")

# ----- TUGADI -----
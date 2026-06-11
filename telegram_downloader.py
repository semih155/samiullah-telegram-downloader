import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

# ====================== OTOMATİK GÜNCELLEME ======================
def paket_guncelle():
    print("\033[96m🔄 Paketler kontrol ediliyor...\033[0m")
    ret = os.system(f"{sys.executable} -m pip install --upgrade --no-cache-dir telethon 2>/dev/null")
    if ret == 0:
        print("\033[92m✔ Güncel.\033[0m")
    else:
        print("\033[93m⚠ Güncelleme başarısız, devam ediliyor...\033[0m")

paket_guncelle()

def kilit_kirici():
    try:
        for f in Path(".").glob("telegram_session*"):
            if f.suffix.startswith(".session") or "-" in f.name:
                try:
                    f.unlink(missing_ok=True)
                except:
                    pass
    except:
        pass

kilit_kirici()

try:
    from telethon import TelegramClient, errors
    from telethon.tl.types import InputDocumentFileLocation
except ImportError:
    print("Telethon kuruluyor...")
    os.system(f"{sys.executable} -m pip install telethon")
    from telethon import TelegramClient, errors
    from telethon.tl.types import InputDocumentFileLocation

# ====================== AYARLAR ======================
ENV_FILE       = ".env_telegram"
SESSION_FILE   = "telegram_session"
STORAGE_PATH   = "/sdcard/Download"
HAFIZA_FILE    = ".indirilenler.json"
LAST_LINK_FILE = ".last_channel.txt"
CHUNK_SIZE     = 512 * 1024  # 512 KB

G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"; W = "\033[97m"
D = "\033[2m"; RS = "\033[0m"; R = "\033[91m"; B = "\033[94m"

def logo_yazdir():
    os.system("clear" if os.name != "nt" else "cls")
    print(f"""{B}
    ╔══════════════════════════════════════╗
    ║  {W}░░ SAMİULLAH DİLSUZ ░░{B}            ║
    ║  {G}⚡ TURBO STABLE MOD v6.6 ⚡{B}         ║
    ╚══════════════════════════════════════╝{RS}
    {C}   Resume Destekli • File Ref Yenileme • Sabit{RS}
    """)

# ====================== PROGRESS BAR ======================
def progress_yazdir(indirilen, boyut, baslangic):
    gecen = time.time() - baslangic or 0.001
    hiz = indirilen / gecen
    yuzde = (indirilen / boyut) * 100 if boyut else 0
    dolu = int(yuzde / 5)
    bar = f"{G}{'🔥' * dolu}{D}{'░' * (20 - dolu)}{RS}"
    sys.stdout.write(
        f"\r  {bar} %{yuzde:.1f} | {C}{hiz/1024/1024:.2f} MB/s{RS} | "
        f"{W}{indirilen/1024/1024:.1f}/{boyut/1024/1024:.1f} MB{RS}  "
    )
    sys.stdout.flush()

# ====================== RESUME DESTEKLİ İNDİRME ======================
async def resume_indir(client, entity, msg_id, hedef_dosya: Path, kol_sayisi: int):
    msg = await client.get_messages(entity, ids=msg_id)
    if not msg:
        raise Exception("Mesaj bulunamadı")

    doc   = msg.media.document
    boyut = doc.size

    YENILE_ARALIK = 50 * 1024 * 1024

    baslangic_offset = 0
    if hedef_dosya.exists():
        mevcut = hedef_dosya.stat().st_size
        baslangic_offset = (mevcut // CHUNK_SIZE) * CHUNK_SIZE
        if baslangic_offset > 0 and baslangic_offset < boyut:
            print(f"\n{Y}⏩ Resume: {baslangic_offset/1024/1024:.1f} MB'dan devam{RS}")
            with open(hedef_dosya, "r+b") as f:
                f.truncate(baslangic_offset)

    if baslangic_offset >= boyut:
        print(f"\n{G}✔ Zaten tam indirilmiş.{RS}")
        return

    mod = "ab" if baslangic_offset > 0 else "wb"
    baslangic  = time.time()
    gosterilen = [0]
    son_yenile = [baslangic_offset]

    print(f"\n{Y}📥 {boyut/1024/1024:.1f} MB — indiriliyor...{RS}")

    with open(hedef_dosya, mod) as f:
        offset = baslangic_offset

        while offset < boyut:
            if offset - son_yenile[0] >= YENILE_ARALIK:
                print(f"\n{C}🔄 Proaktif yenileme ({offset/1024/1024:.0f} MB)...{RS}", end="", flush=True)
                try:
                    taze = await client.get_messages(entity, ids=msg_id)
                    if taze:
                        doc = taze.media.document
                        son_yenile[0] = offset
                        print(f" {G}✔{RS}")
                except Exception as e:
                    print(f" {Y}uyarı: {e}{RS}")

            loc = InputDocumentFileLocation(
                id=doc.id,
                access_hash=doc.access_hash,
                file_reference=doc.file_reference,
                thumb_size=""
            )

            try:
                async for chunk in client.iter_download(
                    loc,
                    offset=offset,
                    request_size=CHUNK_SIZE,
                    dc_id=doc.dc_id
                ):
                    if offset >= boyut:
                        break
                    kalan = boyut - offset
                    if len(chunk) > kalan:
                        chunk = chunk[:kalan]
                    f.write(chunk)
                    f.flush()
                    offset        += len(chunk)
                    gosterilen[0] += len(chunk)
                    progress_yazdir(baslangic_offset + gosterilen[0], boyut, baslangic)

                break

            except (errors.FileReferenceExpiredError, errors.FileReferenceInvalidError):
                print(f"\n{Y}🔄 File reference expire ({offset/1024/1024:.1f} MB) — yenileniyor...{RS}")
                await asyncio.sleep(1)
                taze = await client.get_messages(entity, ids=msg_id)
                if not taze:
                    raise Exception("Mesaj bulunamadı, yenileme başarısız")
                doc = taze.media.document
                son_yenile[0] = offset
                print(f"{G}✔ Yenilendi → {offset/1024/1024:.1f} MB'dan devam{RS}")
                continue

            except errors.FloodWaitError as e:
                print(f"\n{Y}⏳ FloodWait: {e.seconds}s bekleniyor...{RS}")
                await asyncio.sleep(e.seconds + 5)
                continue

    print()

# ====================== WORKER ======================
async def video_worker(worker_id, kuyruk, client, entity, hedef_klasor,
                       hafiza, hafiza_lock, sonuclar, kol_sayisi, sema):
    while True:
        try:
            idx, toplam, msg_id, dosya_adi, boyut = kuyruk.get_nowait()
        except asyncio.QueueEmpty:
            break

        hedef_dosya = hedef_klasor / dosya_adi
        h_key = str(msg_id)

        async with hafiza_lock:
            if h_key in hafiza and hedef_dosya.exists() and hedef_dosya.stat().st_size >= boyut:
                print(f"{D}⏭  [{idx}/{toplam}] Zaten tamam: {dosya_adi}{RS}")
                kuyruk.task_done()
                continue

        print(f"\n{W}[W{worker_id}] [{idx}/{toplam}] 🚀 {dosya_adi}{RS}")
        t0 = time.time()
        basarili = False

        for deneme in range(4):
            async with sema:
                try:
                    await resume_indir(client, entity, msg_id, hedef_dosya, kol_sayisi)

                    sure    = time.time() - t0
                    ort_hiz = (boyut / sure / 1024 / 1024) if sure > 0 else 0

                    async with hafiza_lock:
                        hafiza.add(h_key)
                        Path(HAFIZA_FILE).write_text(json.dumps(list(hafiza), ensure_ascii=False))

                    print(f"{G}✅ [{idx}/{toplam}] Tamamlandı — {sure:.1f}s | {ort_hiz:.2f} MB/s{RS}")
                    sonuclar.append(("ok", dosya_adi))
                    basarili = True
                    break

                except errors.FloodWaitError as e:
                    print(f"\n{Y}⏳ FloodWait: {e.seconds}s (Deneme {deneme+1}/4){RS}")
                    await asyncio.sleep(e.seconds + 5)

                except Exception as e:
                    print(f"\n{R}❌ [{idx}] Deneme {deneme+1}/4 — {type(e).__name__}: {e}{RS}")
                    bekleme = 5 * (deneme + 1)
                    print(f"{Y}  {bekleme}s bekleniyor...{RS}")
                    await asyncio.sleep(bekleme)

        if not basarili:
            print(f"{R}  ❌ {dosya_adi} başarısız. Dosya korundu (sonraki çalıştırmada resume edilir).{RS}")
            sonuclar.append(("hata", dosya_adi))

        kuyruk.task_done()

# ====================== OTURUM ======================
async def oturum_ac(api_id, api_hash, phone):
    client = TelegramClient(SESSION_FILE, api_id, api_hash)
    await client.connect()

    if await client.is_user_authorized():
        print(f"{G}✔ Kayıtlı oturum bulundu.{RS}")
        return client

    print(f"{Y}İlk giriş yapılıyor...{RS}")
    await client.send_code_request(phone)
    kod = input(f"{C}Telegram kodu: {RS}").strip()
    try:
        await client.sign_in(phone, kod)
    except errors.SessionPasswordNeededError:
        sifre = input(f"{C}2FA Şifre: {RS}").strip()
        await client.sign_in(password=sifre)

    print(f"{G}✔ Giriş başarılı!{RS}")
    return client

# ====================== ANA ======================
async def ana_islem():
    logo_yazdir()

    if not Path(ENV_FILE).exists():
        api_id   = input(f"{C}API ID   : {RS}").strip()
        api_hash = input(f"{C}API HASH : {RS}").strip()
        phone    = input(f"{C}Telefon (+90...): {RS}").strip()
        Path(ENV_FILE).write_text(f"API_ID={api_id}\nAPI_HASH={api_hash}\nPHONE={phone}\n")

    conf = dict(line.split('=', 1) for line in Path(ENV_FILE).read_text().splitlines() if '=' in line)

    son_kanal   = Path(LAST_LINK_FILE).read_text().strip() if Path(LAST_LINK_FILE).exists() else ""
    kanal_input = input(f"{C}› Hedef Kanal/Link [{son_kanal}]: {RS}").strip() or son_kanal
    Path(LAST_LINK_FILE).write_text(kanal_input)

    kol_sayisi  = int(input(f"{Y}› Kol sayısı (1-3 önerilir, fazlası flood riski): {RS}") or "2")
    worker_sayi = int(input(f"{Y}› Eşzamanlı video (1 önerilir): {RS}") or "1")
    adet        = int(input(f"{C}› Kaç video? (0 = hepsi): {RS}") or "0")
    sira        = input(f"{C}› Sıra (1=Yeni→Eski | 2=Eski→Yeni): {RS}") or "1"

    client = await oturum_ac(int(conf['API_ID']), conf['API_HASH'], conf['PHONE'])
    entity = await client.get_entity(kanal_input)

    kanal_adi    = re.sub(r'[\\/:*?"<>|]', '', getattr(entity, 'title', 'Kanal')).strip().replace(" ", "_")
    hedef_klasor = Path(STORAGE_PATH) / kanal_adi
    hedef_klasor.mkdir(parents=True, exist_ok=True)

    print(f"{C}📋 Video'lar alınıyor...{RS}")
    video_listesi = []
    async for m in client.iter_messages(
        entity,
        limit=adet if adet > 0 else None,
        reverse=(sira == "2")
    ):
        if m.media and getattr(m.media, 'document', None):
            mime = getattr(m.media.document, 'mime_type', '')
            if mime and 'video' in mime.lower():
                ham_ad    = re.sub(r'[\\/:*?"<>|]', '', (m.message or f"video_{m.id}").split('\n')[0])[:40].strip()
                dosya_adi = (ham_ad or f"video_{m.id}") + ".mp4"
                video_listesi.append((m.id, dosya_adi, m.media.document.size))

    print(f"{G}✔ {len(video_listesi)} video bulundu.{RS}\n")

    if not video_listesi:
        print(f"{R}Video yok.{RS}")
        await client.disconnect()
        return

    hafiza      = set(json.loads(Path(HAFIZA_FILE).read_text())) if Path(HAFIZA_FILE).exists() else set()
    hafiza_lock = asyncio.Lock()
    sonuclar    = []
    sema        = asyncio.Semaphore(worker_sayi)

    kuyruk = asyncio.Queue()
    for idx, (msg_id, dosya_adi, boyut) in enumerate(video_listesi, 1):
        await kuyruk.put((idx, len(video_listesi), msg_id, dosya_adi, boyut))

    workers = [
        asyncio.create_task(
            video_worker(
                i + 1, kuyruk, client, entity,
                hedef_klasor, hafiza, hafiza_lock,
                sonuclar, kol_sayisi, sema
            )
        )
        for i in range(min(worker_sayi, len(video_listesi)))
    ]

    await asyncio.gather(*workers)
    await client.disconnect()

    ok   = sum(1 for s, _ in sonuclar if s == "ok")
    hata = sum(1 for s, _ in sonuclar if s == "hata")
    print(f"\n{G}{'═'*50}")
    print(f"  ✅ Başarılı : {ok}")
    print(f"  ❌ Hatalı   : {hata}")
    print(f"  📁 Klasör   : {hedef_klasor}")
    print(f"{'═'*50}{RS}")

if __name__ == "__main__":
    try:
        asyncio.run(ana_islem())
    except KeyboardInterrupt:
        print(f"\n{R}👋 Kapatıldı.{RS}")
    except Exception as e:
        print(f"\n{R}Beklenmedik hata: {e}{RS}")

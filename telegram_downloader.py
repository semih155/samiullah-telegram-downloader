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
    from telethon.tl.types import InputDocumentFileLocation, DocumentAttributeFilename, PeerChannel
except ImportError:
    print("Telethon kuruluyor...")
    os.system(f"{sys.executable} -m pip install telethon")
    from telethon import TelegramClient, errors
    from telethon.tl.types import InputDocumentFileLocation, DocumentAttributeFilename, PeerChannel

# ====================== AYARLAR ======================
ENV_FILE       = ".env_telegram"
SESSION_FILE   = "telegram_session"
STORAGE_PATH   = "/sdcard/Download"
HAFIZA_FILE    = ".indirilenler.json"
LAST_LINK_FILE = ".last_channel.txt"

# Standart (ücretsiz) hesaplar için chunk boyutu
CHUNK_SIZE_STANDARD = 512 * 1024   # 512 KB
# Telegram Premium (VIP) hesaplar için chunk boyutu — daha az round-trip, daha yüksek hız
CHUNK_SIZE_PREMIUM  = 1024 * 1024  # 1 MB

# Bu, çalışma anında premium seçimine göre ayarlanır (varsayılan: standart)
CHUNK_SIZE = CHUNK_SIZE_STANDARD

G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"; W = "\033[97m"
D = "\033[2m"; RS = "\033[0m"; R = "\033[91m"; B = "\033[94m"

def logo_yazdir():
    os.system("clear" if os.name != "nt" else "cls")
    print(f"""{B}
    ╔══════════════════════════════════════╗
    ║  {W}░░ SAMİULLAH DİLSUZ ░░{B}            ║
    ║  {G}⚡ TURBO STABLE MOD v7.2 ⚡{B}         ║
    ╚══════════════════════════════════════╝{RS}
    {C}   Resume Destekli • File Ref Yenileme • Link ile Tekli İndirme • VIP Hız Modu{RS}
    """)

# ====================== LINK PARSE ======================
def link_parse(girdi: str):
    """
    Döndürür: (ozel_mi, kimlik, mesaj_id)
    - ozel_mi=True  -> kimlik bir kanal numarasıdır (t.me/c/NUMARA/ID)
    - ozel_mi=False -> kimlik bir username veya davet linkidir
    - mesaj_id=None -> tüm kanal modu (eski davranış)
    - mesaj_id='...' -> tekli mesaj indirme modu
    """
    girdi = girdi.strip()

    # t.me/c/1234567890/123  (private kanal, sayısal id)
    m = re.match(r'(?:https?://)?(?:www\.)?t(?:elegram)?\.me/c/(\d+)(?:/(\d+))?/?(?:\?.*)?$', girdi)
    if m:
        return True, m.group(1), m.group(2)

    # t.me/kanaladi/123  (public kanal + opsiyonel mesaj id)
    m = re.match(r'(?:https?://)?(?:www\.)?t(?:elegram)?\.me/([A-Za-z0-9_]+)(?:/(\d+))?/?(?:\?.*)?$', girdi)
    if m:
        return False, m.group(1), m.group(2)

    # kanaladi/123 (linksiz kısayol)
    m = re.match(r'^([A-Za-z0-9_]+)/(\d+)$', girdi)
    if m:
        return False, m.group(1), m.group(2)

    # sade username, davet linki (+hash), veya @kullaniciadi -> eski davranış
    return False, girdi, None

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

# ====================== DOSYA ADI/UZANTI YARDIMCI ======================
MIME_UZANTI = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "image/gif": ".gif", "video/mp4": ".mp4", "video/quicktime": ".mov",
    "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/ogg": ".ogg",
    "application/pdf": ".pdf", "application/zip": ".zip",
    "application/x-rar-compressed": ".rar", "application/vnd.rar": ".rar",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}

def dosya_adi_uret(msg):
    doc = msg.media.document
    mime = getattr(doc, 'mime_type', '') or ''

    orijinal_ad = None
    for attr in getattr(doc, 'attributes', []):
        if isinstance(attr, DocumentAttributeFilename):
            orijinal_ad = attr.file_name
            break

    if orijinal_ad:
        temiz = re.sub(r'[\\/:*?"<>|]', '', orijinal_ad).strip()
        return temiz or f"dosya_{msg.id}"

    ham_ad = re.sub(r'[\\/:*?"<>|]', '', (msg.message or f"dosya_{msg.id}").split('\n')[0])[:40].strip()
    uzanti = MIME_UZANTI.get(mime, "")
    if not uzanti and mime:
        alt = mime.split("/")[-1]
        uzanti = f".{alt}" if alt else ""
    return (ham_ad or f"dosya_{msg.id}") + uzanti

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

    print(f"\n{Y}📥 {boyut/1024/1024:.1f} MB — indiriliyor... ({CHUNK_SIZE//1024} KB parça){RS}")

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

# ====================== VIP (PREMIUM) HIZ MODU ======================
async def vip_modu_belirle(client):
    """
    Kullanıcının hesabı gerçekten Telegram Premium mu diye API üzerinden kontrol eder
    ve buna göre CHUNK_SIZE'ı ayarlar. Kontrol başarısız olursa kullanıcıya sorar.
    """
    global CHUNK_SIZE

    premium_mi = None
    try:
        me = await client.get_me()
        premium_mi = bool(getattr(me, 'premium', False))
    except Exception:
        premium_mi = None

    if premium_mi is None:
        secim = (input(f"{C}› Telegram Premium (VIP) hesabınız var mı? (e/h) [h]: {RS}").strip().lower() or "h")
        premium_mi = secim.startswith("e")
    else:
        etiket = f"{G}Evet{RS}" if premium_mi else f"{Y}Hayır{RS}"
        print(f"{C}› Telegram Premium durumu (otomatik tespit edildi): {etiket}")
        secim = (input(f"{C}  VIP hız modunu kullanmak istiyor musunuz? (e/h) [{'e' if premium_mi else 'h'}]: {RS}").strip().lower())
        if secim:
            premium_mi = secim.startswith("e")

    if premium_mi:
        CHUNK_SIZE = CHUNK_SIZE_PREMIUM
        print(f"{G}⚡ VIP Hız Modu AKTİF — {CHUNK_SIZE//1024} KB parça boyutu kullanılacak.{RS}")
    else:
        CHUNK_SIZE = CHUNK_SIZE_STANDARD
        print(f"{C}Standart mod — {CHUNK_SIZE//1024} KB parça boyutu kullanılacak.{RS}")

    return premium_mi

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
    kanal_input = input(f"{C}› Hedef Kanal/Link (kanal linki veya tekli mesaj linki, örn. t.me/kanal/123) [{son_kanal}]: {RS}").strip() or son_kanal
    Path(LAST_LINK_FILE).write_text(kanal_input)

    ozel_mi, kimlik, mesaj_id = link_parse(kanal_input)

    client = await oturum_ac(int(conf['API_ID']), conf['API_HASH'], conf['PHONE'])

    # VIP (Premium) hız modunu belirle — CHUNK_SIZE burada set edilir
    await vip_modu_belirle(client)

    if ozel_mi:
        entity = await client.get_entity(PeerChannel(int(f"-100{kimlik}")))
    else:
        entity = await client.get_entity(kimlik)

    kanal_adi    = re.sub(r'[\\/:*?"<>|]', '', getattr(entity, 'title', 'Kanal')).strip().replace(" ", "_")
    hedef_klasor = Path(STORAGE_PATH) / kanal_adi
    hedef_klasor.mkdir(parents=True, exist_ok=True)

    if mesaj_id:
        # ---- TEKLİ MESAJ İNDİRME MODU ----
        print(f"{C}📋 Link üzerinden tekli mesaj alınıyor (ID: {mesaj_id})...{RS}")
        m = await client.get_messages(entity, ids=int(mesaj_id))
        if not m or not (m.media and getattr(m.media, 'document', None)):
            print(f"{R}Bu linkte indirilebilir bir dosya bulunamadı.{RS}")
            await client.disconnect()
            return

        dosya_adi = dosya_adi_uret(m)
        video_listesi = [(m.id, dosya_adi, m.media.document.size)]
        kol_sayisi  = int(input(f"{Y}› Kol sayısı (1-3 önerilir, fazlası flood riski): {RS}") or "2")
        worker_sayi = 1
    else:
        # ---- TÜM KANAL MODU (eski davranış) ----
        print(f"\n{Y}› Ne indirilsin?{RS}")
        print(f"  {W}1{RS} = Sadece video")
        print(f"  {W}2{RS} = Tüm dosyalar (video, foto, pdf, zip, mp3, vs. — ne varsa){RS}")
        mod_secim = (input(f"{C}› Seçim [1]: {RS}").strip() or "1")
        tum_dosyalar = (mod_secim == "2")

        kol_sayisi  = int(input(f"{Y}› Kol sayısı (1-3 önerilir, fazlası flood riski): {RS}") or "2")
        worker_sayi = int(input(f"{Y}› Eşzamanlı indirme (1 önerilir): {RS}") or "1")
        adet        = int(input(f"{C}› Kaç dosya? (0 = hepsi): {RS}") or "0")
        sira        = input(f"{C}› Sıra (1=Yeni→Eski | 2=Eski→Yeni): {RS}") or "1"

        print(f"{C}📋 {'Dosyalar' if tum_dosyalar else 'Videolar'} alınıyor...{RS}")
        video_listesi = []
        async for m in client.iter_messages(
            entity,
            limit=adet if adet > 0 else None,
            reverse=(sira == "2")
        ):
            if not (m.media and getattr(m.media, 'document', None)):
                continue

            mime = getattr(m.media.document, 'mime_type', '') or ''

            if not tum_dosyalar and 'video' not in mime.lower():
                continue

            dosya_adi = dosya_adi_uret(m)
            video_listesi.append((m.id, dosya_adi, m.media.document.size))

        print(f"{G}✔ {len(video_listesi)} dosya bulundu.{RS}\n")

    if not video_listesi:
        print(f"{R}Dosya yok.{RS}")
        await client.disconnect()
        return

    hafiza      = set(json.loads(Path(HAFIZA_FILE).read_text())) if Path(HAFIZA_FILE).exists() else set()
    hafiza_lock = asyncio.Lock()
    sonuclar    = []
    sema        = asyncio.Semaphore(worker_sayi)

    kuyruk = asyncio.Queue()
    for idx, (msg_id2, dosya_adi, boyut) in enumerate(video_listesi, 1):
        await kuyruk.put((idx, len(video_listesi), msg_id2, dosya_adi, boyut))

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

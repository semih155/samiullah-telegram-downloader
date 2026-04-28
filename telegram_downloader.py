import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

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
    os.system(f"{sys.executable} -m pip install telethon cryptg")
    from telethon import TelegramClient, errors
    from telethon.tl.types import InputDocumentFileLocation

# ====================== AYARLAR ======================
ENV_FILE       = ".env_telegram"
SESSION_FILE   = "telegram_session"
STORAGE_PATH   = "/sdcard/Download"
HAFIZA_FILE    = ".indirilenler.json"
LAST_LINK_FILE = ".last_channel.txt"

G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"; W = "\033[97m"
D = "\033[2m"; RS = "\033[0m"; R = "\033[91m"; B = "\033[94m"

def logo_yazdir():
    os.system("clear" if os.name != "nt" else "cls")
    print(f"""{B}
    ╔══════════════════════════════════════╗
    ║  {W}░░ SAMİULLAH DİLSUZ ░░{B}            ║
    ║  {G}⚡ TURBO STABLE MOD v6.4 ⚡{B}         ║
    ╚══════════════════════════════════════╝{RS}
    {C}   Tek Oturum • Chunk + Retry • Sabit Çalışma{RS}
    """)

# ====================== İNDİRME FONKSİYONLARI ======================
async def chunk_indir(client, msg, hedef_dosya: Path, kol_sayisi: int):
    """Daha güvenli chunk indirme (Telegram limitlerine uyumlu)"""
    doc = msg.media.document
    boyut = doc.size
    CHUNK_SIZE = 512 * 1024  # Telegram önerisi
    parca = max(boyut // kol_sayisi, CHUNK_SIZE * 4)  # çok küçük parça olmasın

    gecici = [hedef_dosya.with_suffix(f".part{i}") for i in range(kol_sayisi)]
    indirilen = [0]
    baslangic = time.time()
    print_lock = asyncio.Lock()

    async def goster():
        async with print_lock:
            gecen = time.time() - baslangic or 0.001
            hiz = indirilen[0] / gecen
            yuzde = (indirilen[0] / boyut) * 100 if boyut else 0
            dolu = int(yuzde / 5)
            bar = f"{G}{'🔥' * dolu}{D}{'░' * (20 - dolu)}{RS}"
            sys.stdout.write(
                f"\r  {bar} %{yuzde:.1f} | {C}{hiz/1024/1024:.2f} MB/s{RS} | "
                f"{W}{indirilen[0]/1024/1024:.1f}/{boyut/1024/1024:.1f} MB{RS}  "
            )
            sys.stdout.flush()

    async def kol_indir(idx):
        bas = idx * parca
        bit = min((idx + 1) * parca, boyut) if idx < kol_sayisi - 1 else boyut

        loc = InputDocumentFileLocation(
            id=doc.id, access_hash=doc.access_hash,
            file_reference=doc.file_reference, thumb_size=""
        )

        with open(gecici[idx], "wb") as f:
            offset = bas
            async for chunk in client.iter_download(
                loc, offset=offset, request_size=CHUNK_SIZE, dc_id=doc.dc_id
            ):
                if offset >= bit:
                    break
                kalan = bit - offset
                if len(chunk) > kalan:
                    chunk = chunk[:kalan]
                f.write(chunk)
                indirilen[0] += len(chunk)
                await goster()
                offset += len(chunk)

    print(f"\n{Y}📦 {kol_sayisi} kol başlatılıyor... ({boyut/1024/1024:.1f} MB){RS}")
    await asyncio.gather(*[kol_indir(i) for i in range(kol_sayisi)])

    # Birleştir
    print(f"\n{C}🔗 Birleştiriliyor...{RS}", end="", flush=True)
    with open(hedef_dosya, "wb") as son:
        for p in gecici:
            if p.exists():
                son.write(p.read_bytes())
                p.unlink(missing_ok=True)
    print(f" {G}✔{RS}")

async def standart_indir(client, msg, hedef_dosya: Path):
    boyut = msg.media.document.size
    bas = time.time()

    def cb(mevcut, toplam):
        gecen = time.time() - bas or 0.001
        hiz = mevcut / gecen
        yuzde = (mevcut / boyut) * 100 if boyut else 0
        dolu = int(yuzde / 5)
        bar = f"{G}{'█' * dolu}{D}{'░' * (20 - dolu)}{RS}"
        sys.stdout.write(
            f"\r  {bar} %{yuzde:.1f} | {C}{hiz/1024/1024:.2f} MB/s{RS} | "
            f"{W}{mevcut/1024/1024:.1f}/{boyut/1024/1024:.1f} MB{RS}  "
        )
        sys.stdout.flush()

    await client.download_media(msg, file=str(hedef_dosya), progress_callback=cb)

# ====================== WORKER ======================
async def video_worker(worker_id, kuyruk, client, hedef_klasor, hafiza, hafiza_lock, sonuclar, kol_sayisi, sema):
    while True:
        try:
            idx, toplam, msg = kuyruk.get_nowait()
        except asyncio.QueueEmpty:
            break

        ham_ad = re.sub(r'[\\/:*?"<>|]', '', (msg.message or f"video_{msg.id}").split('\n')[0])[:40]
        dosya_adi = ham_ad + ".mp4"
        hedef_dosya = hedef_klasor / dosya_adi
        h_key = str(msg.id)

        async with hafiza_lock:
            if h_key in hafiza and hedef_dosya.exists() and hedef_dosya.stat().st_size > 0:
                print(f"{D}⏭  [{idx}/{toplam}] Zaten tamam: {dosya_adi}{RS}")
                kuyruk.task_done()
                continue

        print(f"\n{W}[W{worker_id}] [{idx}/{toplam}] 🚀 {dosya_adi}{RS}")
        t0 = time.time()

        for deneme in range(3):  # 3 kez retry
            async with sema:
                try:
                    boyut = msg.media.document.size
                    if boyut > 10 * 1024 * 1024 and kol_sayisi > 1:  # büyük dosyalar için chunk
                        await chunk_indir(client, msg, hedef_dosya, kol_sayisi)
                    else:
                        await standart_indir(client, msg, hedef_dosya)

                    sure = time.time() - t0
                    ort_hiz = (boyut / sure / 1024 / 1024) if sure > 0 else 0

                    async with hafiza_lock:
                        hafiza.add(h_key)
                        Path(HAFIZA_FILE).write_text(json.dumps(list(hafiza), ensure_ascii=False))

                    print(f"\n{G}✅ [{idx}/{toplam}] Tamamlandı — {sure:.1f}s | {ort_hiz:.2f} MB/s{RS}")
                    sonuclar.append(("ok", dosya_adi))
                    break

                except errors.FloodWaitError as e:
                    print(f"\n{Y}⏳ FloodWait: {e.seconds}s bekleniyor...{RS}")
                    await asyncio.sleep(e.seconds + 3)
                    if deneme == 2:
                        sonuclar.append(("hata", dosya_adi))

                except (errors.FileReferenceExpiredError, errors.FileReferenceInvalidError):
                    print(f"\n{Y}🔄 File reference yenileniyor...{RS}")
                    try:
                        taze_msg = await client.get_messages(msg.peer_id, ids=msg.id)
                        msg = taze_msg  # güncelle
                        continue
                    except Exception as e2:
                        print(f"{R}Yenileme başarısız: {e2}{RS}")
                        sonuclar.append(("hata", dosya_adi))
                        break

                except Exception as e:
                    print(f"\n{R}❌ [{idx}] Hata: {type(e).__name__} - {e}{RS}")
                    # Temizlik
                    for p in hedef_klasor.glob(f"{hedef_dosya.stem}.part*"):
                        p.unlink(missing_ok=True)
                    if hedef_dosya.exists() and hedef_dosya.stat().st_size == 0:
                        hedef_dosya.unlink(missing_ok=True)
                    if deneme == 2:
                        sonuclar.append(("hata", dosya_adi))
                    await asyncio.sleep(2)

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
        api_id = input(f"{C}API ID   : {RS}").strip()
        api_hash = input(f"{C}API HASH : {RS}").strip()
        phone = input(f"{C}Telefon (+90...): {RS}").strip()
        Path(ENV_FILE).write_text(f"API_ID={api_id}\nAPI_HASH={api_hash}\nPHONE={phone}\n")

    conf = dict(line.split('=', 1) for line in Path(ENV_FILE).read_text().splitlines() if '=' in line)

    son_kanal = Path(LAST_LINK_FILE).read_text().strip() if Path(LAST_LINK_FILE).exists() else ""
    kanal_input = input(f"{C}› Hedef Kanal/Link [{son_kanal}]: {RS}").strip() or son_kanal
    Path(LAST_LINK_FILE).write_text(kanal_input)

    kol_sayisi = int(input(f"{Y}› Chunk kol sayısı (4-8 önerilir): {RS}") or "6")
    worker_sayi = int(input(f"{Y}› Eşzamanlı video (1-3 önerilir, flood olmasın): {RS}") or "2")
    adet = int(input(f"{C}› Kaç video indirelim? (0 = hepsi): {RS}") or "0")
    sira = input(f"{C}› Sıra (1=Yeni → Eski | 2=Eski → Yeni): {RS}") or "1"

    client = await oturum_ac(int(conf['API_ID']), conf['API_HASH'], conf['PHONE'])

    entity = await client.get_entity(kanal_input)
    kanal_adi = re.sub(r'[\\/:*?"<>|]', '', getattr(entity, 'title', 'Kanal')).strip().replace(" ", "_")
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
                video_listesi.append(m)

    print(f"{G}✔ {len(video_listesi)} video bulundu.{RS}\n")

    if not video_listesi:
        print(f"{R}Video yok.{RS}")
        await client.disconnect()
        return

    hafiza = set(json.loads(Path(HAFIZA_FILE).read_text())) if Path(HAFIZA_FILE).exists() else set()
    hafiza_lock = asyncio.Lock()
    sonuclar = []
    sema = asyncio.Semaphore(worker_sayi)

    kuyruk = asyncio.Queue()
    for idx, msg in enumerate(video_listesi, 1):
        await kuyruk.put((idx, len(video_listesi), msg))

    workers = [
        asyncio.create_task(video_worker(i+1, kuyruk, client, hedef_klasor, hafiza, hafiza_lock, sonuclar, kol_sayisi, sema))
        for i in range(min(worker_sayi, len(video_listesi)))
    ]

    await asyncio.gather(*workers)
    await client.disconnect()

    ok = sum(1 for s, _ in sonuclar if s == "ok")
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
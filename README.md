# SplitUZ

CBU Coding Hackathon 2026 uchun ishlaydigan MVP: istalgan guruh xarajatlari to‘plamini import qilish, avval bajarilgan qarz yopishlarini hisobga olgan aniq net-balans va o‘tkazmalar sonini kamaytirish.

ERD va SQL DDL: `docs/ERD.png`, `docs/ERD.md`, `docs/schema.sql`. Yakuniy tekshiruv: `SUBMISSION_CHECKLIST.md`. `dataset/` ichida maxfiy ma’lumotlardan holi, sun’iy demo ma’lumotlar bor. Ular ilovani sinash uchun yaratilgan va real shaxslar yoki moliyaviy yozuvlardan olinmagan.

## Tez ishga tushirish

Docker Desktop o‘rnatilgan va ishga tushirilgan bo‘lishi kerak.

```bash
docker compose up --build
```

Brauzerda http://localhost:8000 manzilini oching. Har bir ishga tushirishda `dataset/` papkasidagi beshta CSV yagona haqiqat manbai sifatida avtomatik import qilinadi. Shu sababli yopiq datasetni almashtirish PostgreSQL volume ichida eski ma’lumotlarni qoldirmaydi. Natija `natija/balanslar.csv` fayliga yoziladi.

Qayta build qilmasdan takroriy ishga tushirish:

```bash
docker compose up
```

## 

1. Istalgan guruh va ishtirokchini tanlang: markazdagi raqam uning net-balansini ko‘rsatadi.
2. Minimal o‘tkazmalar ro‘yxati hamda exact/greedy taqqoslash hisoblagichini ko‘rsating.
3. Xarajatni to‘rtta bo‘lish usulidan biri orqali qo‘shing. Foizlarda qiymatlar yig‘indisi 100, aniq summalar yoki pozitsiyalarda esa xarajat summasiga teng bo‘lishi kerak.
4. O‘tkazma yonidagi demo QR kodni oching.
5. «Natijani yuklab olish» tugmasini bosing va `natija/balanslar.csv` faylini ko‘rsating.
6. «CSV import» orqali yopiq datasetning aynan beshta faylini tanlang; interfeys avtomatik ravishda yangi ma’lumotlarga moslashadi.

MVPda ro‘yxatdan o‘tish o‘rniga foydalanuvchi dinamik ro‘yxatdan tanlanadi. Hech bir ID, guruh hajmi yoki summa kodga hardcode qilinmagan.

## 

Asl o‘zbekcha ustun nomlariga ega aynan `groups.csv`, `members.csv`, `expenses.csv`, `expense_shares.csv`, `settlements.csv` fayllari kutiladi. Import atomar bajariladi: avval aniq ustunlar, bo‘sh qiymatlar, barcha PK/bog‘lanishlar, ulush guruhining xarajat guruhiga mosligi, `BIGINT` diapazoni, valyuta, usullar, statuslar, flaglar va xarajat ulushlari yig‘indisi tekshiriladi; faqat shundan keyin joriy dataset almashtiriladi.

Demo serverni himoyalovchi limitlar: har bir CSV uchun ko‘pi bilan 10 MiB, jami 40 MiB va har bir faylda 250 000 qator. Bu kutilayotgan yopiq datasetdan ancha katta, ammo xotira yoki diskning tasodifiy to‘lib qolishini oldini oladi.

O‘chirilgan xarajatlar (`ochirilgan` qiymati `yo'q` ga teng bo‘lmasa) balansda qatnashmaydi. Settlements ichidan faqat `tasdiqlangan` statusi hisobga olinadi.

## Buyruqlar

```bash
make run       # ilovani ishga tushirish
make test      # python -m pytest orqali avtotestlar
make verify    # ochiq datasetni mavjud kalit bilan 1 so‘mgacha solishtirish
make import    # dataset/ fayllarini qayta import qilish
make fresh     # faqat DB volume’ni o‘chirib, toza ishga tushirish
```

`make` mavjud bo‘lmasa, `Makefile` ichidagi teng kuchli buyruqlardan foydalaning.

## Tuzilma

```text
app/
  algorithms.py   # two-heap greedy va exact branch-and-bound
  services.py     # import, balans, yaxlitlash, tranzaksion amallar
  models.py       # normallashtirilgan SQL model
  main.py         # FastAPI va API
  templates/      # RU/UZ qo‘llab-quvvatlovchi bitta asosiy ekran
  static/         # moslashuvchan UI
dataset/          # kiruvchi CSV fayllar
natija/           # majburiy balanslar.csv
tests/            # algoritmlar, invariantlar va etalon tekshiruvi
```

## Parallel yozuvlar xavfsizligi

Xarajat yoki settlement qo‘shish DB tranzaksiyasida bajariladi. `SELECT ... FOR UPDATE` guruh qatorini bloklaydi, shuning uchun bitta guruhdagi ikkita bir vaqtdagi o‘zgarish ketma-ket bajariladi. Xarajat va barcha normallashtirilgan ulushlar birgalikda saqlanadi yoki to‘liq rollback qilinadi. PostgreSQL tashqi kalitlar va ma’lumotlar yaxlitligini ta’minlaydi.

QR kod faqat demo to‘lov satrini saqlaydi va bank API’siga murojaat qilmaydi.

## Demo rejimidagi himoya choralari

- CSP va import qilingan matnni xavfsiz ekranga chiqarish stored XSS hujumini bloklaydi;
- brauzerdan kelgan cross-site POST so‘rovlari rad etiladi;
- pulga oid cheklovlar importer va DB `CHECK` constraintlarida takrorlangan;
- exact branch-and-bound vaqt/tugun limitiga ega va limit tugaganda halol belgi bilan xavfsiz greedy natijasini qaytaradi;
- `/health` haqiqiy DB ulanishini tekshiradi, Compose esa DB va app holatini nazorat qiladi.

Ilova `localhost`da lokal namoyish qilish uchun mo‘ljallangan. Haqiqiy ko‘p foydalanuvchili production nashri to‘liq autentifikatsiya/RBAC va production secretlarni talab qiladi.

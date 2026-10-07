# Arxitektura va algoritmik qarorlar

## 1. Net-balans

Har bir ishtirokchi uchun UZSdagi butun sonli formula ishlatiladi:

```text
net = to‘langan faol xarajatlar − shaxsiy ulushlar
      + yuborilgan tasdiqlangan settlements
      − qabul qilingan tasdiqlangan settlements
```

Musbat qiymat ishtirokchiga pul qaytarilishi kerakligini, manfiy qiymat esa uning qarzdorligini anglatadi. Qarzdordan kreditorga yuborilgan settlement ikkala ishtirokchini ham nolga yaqinlashtiradi: yuboruvchiga summa qo‘shiladi, qabul qiluvchidan esa ayiriladi.

Sababi: agregatsiya ma’lumotlarning iqtisodiy ma’nosini to‘g‘ridan-to‘g‘ri takrorlaydi va keraksiz juft qarzlarni qayta yaratmaydi. Kirish va chiqish qiymatlari butun so‘mda berilgani sababli barcha summalar `float` yoki `decimal` emas, `BIGINT` sifatida saqlanadi.

Murakkablik: vaqt `O(M + E + S)`, xotira `O(M)`; bu yerda `M` — ishtirokchilar, `E` — ulush/xarajat qatorlari, `S` — qarz yopishlari. DB agregatsiyalarida guruh indekslari ishlatiladi.

Chegaraviy holatlar:

- operatsiyasiz ishtirokchi 0 oladi;
- o‘chirilgan xarajat o‘z ulushlari bilan birga chiqarib tashlanadi;
- faqat tasdiqlangan settlements hisobga olinadi;
- payer o‘z xarajatida ulushga ega bo‘lishi mumkin;
- har bir guruhdan keyin qat’iy `sum(net) == 0` invarianti tekshiriladi;
- xarajat ulushlari bir so‘mgacha tenglashmasa, import rad etiladi.

Patternlar: Service Layer hisob-kitobni HTTP qatlamidan ajratadi; Unit of Work SQLAlchemy tranzaksiyasi orqali amalga oshiriladi; normallashtirilgan `expense_shares` havolalar yaxlitligini ta’minlaydi.

## 2. Ikki heap asosidagi greedy

Qarzdorlar min-heap ichida manfiy balans ko‘rinishida, kreditorlar esa musbat balansning manfiy qiymati ko‘rinishida saqlanadi. Har bir qadamda eng katta qarzdor va kreditor olinadi, `min(debt, credit)` miqdori o‘tkaziladi, qoldiq heapga qaytariladi. ID barqaror tie-breaker vazifasini bajaradi, shu sababli natija deterministik.

Murakkablik: ko‘pi bilan `n−1` ta o‘tkazma; har bir qadam heap amallarini bajaradi, jami vaqt `O(n log n)` va xotira `O(n)`.

Chegaraviy holatlar: nol balansli ishtirokchilar heapga kiritilmaydi; bo‘sh yoki to‘liq yopilgan guruh bo‘sh ro‘yxat beradi; balanslanmagan kirish darhol rad etiladi; har bir o‘tkazma qat’iy musbat.

Greedy juda tez va qarzlarni to‘g‘ri yopishni kafolatlaydi, ammo har doim global minimal o‘tkazmalar sonini bermaydi — bu masala murakkab kombinatorik optimallashtirishga teng.

## 3. Exact branch-and-bound (bonus)

Nol bo‘lmagan ishtirokchilari 12 tagacha bo‘lgan guruhlarda qarzdor va kreditorlarning ruxsat etilgan mosliklari state rollback bilan ko‘rib chiqiladi. Joriy greedy natijasi yuqori chegara sifatida ishlatiladi; qoldig‘i bir xil simmetrik shoxlar o‘tkazib yuboriladi, joriy rekorddan yaxshi bo‘lmagan shoxlar kesiladi. Qidiruv 0.5 soniya va 200 000 tugun bilan chegaralangan: budjet tugasa, `is_exact=false` belgisi bilan to‘g‘ri greedy natijasi qaytariladi. UI haqiqiy rejimni ko‘rsatadi, shu sababli heuristic fallback uchun global minimum da’vo qilinmaydi.

Eng yomon holatdagi murakkablik eksponensial bo‘lib, aniq minimallashtirishning NP-hard tabiatiga mos keladi; eng yaxshi marshrutni hisobga olmaganda xotira `O(n)`. UI ikkala o‘tkazmalar sonini ham ko‘rsatadi — exact kamroq o‘tkazma topsa, ustunlik tushunarli tarzda namoyon bo‘ladi.

## 4. Deterministik yaxlitlash

`teng` va `foiz` usullari uchun eng katta qoldiqlar metodi qo‘llanadi: avval butun pastki qism olinadi, so‘ng qolgan so‘mlar kasr qismi eng katta ishtirokchilarga beriladi; tenglik saralangan `member_id` orqali yechiladi. Shu sababli ulushlar yig‘indisi har doim xarajatga aniq teng va takroriy hisob bir xil natija beradi. Teng ulushlarda qoldiq round-robin usulida taqsimlanadi.

## 5. Parallel ishlash va import

Guruh o‘zgartirilganda uning qatori `SELECT FOR UPDATE` orqali bloklanadi; expense va shares bitta tranzaksiyada yoziladi. Bu qisman yozuv va ikki foydalanuvchi o‘rtasidagi race condition’ni oldini oladi. Import avval to‘liq validatsiya qilinadi, bayt/qator limitlari tekshiriladi, so‘ng beshta jadval bitta tranzaksiyada almashtiriladi. Cross-group shares ham validatsiya, ham composite FK orqali bloklanadi. Eksport barcha guruhlarni to‘rtta set-based so‘rov bilan agregatsiya qiladi, noyob vaqtinchalik faylga yozadi va atomar qayta nomlaydi.

## 6. Texnologiyalar steki

FastAPI qisqa va typed API beradi; PostgreSQL haqiqiy tranzaksiyalar, row lock va constraintlarni ta’minlaydi; SQLAlchemy hisob-kitoblarni SQLite’da test qilish imkonini saqlaydi; Jinja + vanilla JS alohida frontend buildsiz bitta tezkor ekranni beradi. Docker Compose ilovani bitta buyruq bilan ishga tushiradi.

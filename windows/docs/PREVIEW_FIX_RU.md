# Предпросмотр0.1.2

Отчёт пользователя Videojet6330_Diagnostics_20261106_170406_573_preview.zip: связь192.168.1.251:3001 установлена, текущее задание SingleQR 30mm Bold прочитано, ответ на RequestBitmap — FNF (IID8352f878-e0ce-40fa-a357-49c660250f7b), BMP не получен. Изменения не запрашивались.

В0.1.1 RequestBitmap использовал имя JOB, flags0,head1,width640,height256. По firmware ZBC2.dll446C007C flagbit0 выбирает генерацию предпросмотра; приflags0 запрос идёт как поиск обычного bitmap-файла. Поэтому FNF не доказывает отсутствие самого JOB.

Штатный CLARiTYConfig.exe:0x42BE94 пишетflags0x0F,0x42BE9B — head1,0x42BEA4 — нулевыеwidth/height;0x42BF42 ссылается на CurrentImage.bmp;0x42BF62 используетFT_BITMAP3; вызовRequestFile по0x42BF70. В0.1.2 эти параметры передаются через IZBC2MasterSession.RequestBitmap,slot56. Камерный флаг0x200 и GIF0x100 не установлены. Запрос не запускает печать.

Кодек запросов сопоставлен с сохранённой раскладкой FRU5032; регрессионный fixture находится в tests/preview_recipe.json и проверяется SELFTEST. Нативные SendFile/SelectJob не менялись. Исправленный preview пока не проверен на аппарате; новый отчёт должен подтвердить получениеBMP.

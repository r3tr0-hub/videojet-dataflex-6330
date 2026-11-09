# Счётчик14, цикл печати и восстановление

Полная обычная цепочка установлена:

`driver start(mask1)` → `LocalPrintheadProtocol.PrintStarted` → `Imaging/UpdateCounterFields` → ImageMgr observer callback12 → event main+0x3710 → worker `0x456eb1d4` → ICiffUpdater.UpdateSynchronous → ICiffSelection.UpdateFields(flags2/3) → расчёт NextValue → перенос CurrentValue/global map → dirty → snapshot RTC/XML.

Это логический расход значения по запросу начала цикла, который обрабатывается другим потоком. Нельзя приравнять его к успешному физическому нанесению или читаемому коду. Безусловный +1 также неверен: ParentCounter, PrintsPerCount и rollover меняют поведение. Когда выбранный CIFF-счётчик имеет GlobalID14, второй проход обновляет именно global map[14], откуда DataFile затем получает индекс строки.

## Основные результаты

| Вопрос SCADA | Подтверждено ARM-кодом | Остаточная граница |
|---|---|---|
| Где изменяется14 | CiffSelect NextValue→CurrentValue→global map, `0x45918264/29c/2f0` | Значение текущего runtime отсутствует в образе |
| Связь с печатью | Обычный запрос обновления исходит из start; цепочка ImageMgr замкнута | Другой поток может выполнить update позже физического complete |
| Успешность печати | Complete и Abort — раздельные локальные ветки | Ни complete, ни InPrintCycle=0 не доказывают читаемость |
| Повтор start | Worker подавляет `[1,1]`; после complete/abort start разрешён снова | Поведение драйвера/импульсов и exactly-once не доказано |
| Ошибка обновления | Snapshot идёт до проверки отрицательного HRESULT | Ошибка не доказывает rollback; внешняя компенсация не исключена |
| Сохранение | RTC1: IOCTL222004/222008; иначе два XML и writer thread | Физическая стойкость при внезапном питании не доказана |
| Restart | Сначала compact backing, затем более новый из CurrentCounts.1/2.xml | В поставке нет ни этих файлов, ни RTC dump |
| Reset | RemoveOldCountFiles не очищает существующий global map; ResetImageData не равен resetglobal14 | Нельзя использовать эти имена как доказательство нулевого счётчика |

## Файлы

- `ImageMgr_counter_binding_ru.md` — замкнутая привязка start к commit, включая критическое смещение COM observer main+4.
- `ciffselection_counter_ru.md` — global map, двухпроходный update, ParentCounter, PrintsPerCount, RTC/XML, restart/reset.
- `ciff_counter_ru.md` — CIFF счётчики и native ParentCounter setter.
- `print_cycle_ru.md` — драйверные маски, начало/конец/abort и условия запроса.
- `ImageMgr_counter_binding_evidence.asm`, `CiffSelect_counter_evidence.asm`, `ciff_counter_evidence.asm`, `ciffselection_vtable.json` — точные адреса и машинный код.
- `verify_cycle_native.py`, `native_cycle_results.json` — воспроизводимая offline ARM-проверка 8 последовательностей масок, start/complete/abort и отрицательных контролей. Последний запуск: PASS.

Эмуляция использует заданные маски драйвера и явные stub callbacks, не обращается к устройству и не является тестом механики. Альтернативный LPP режим NextSyncUpdateReq (bit0x400) и очередь ImageMgr при main+0x3794!=0 не получили эквивалентного полного анализа временного порядка; эти режимы отмечены отдельно, а не перенесены автоматически на доказанную обычную ветку.

# Замкнутая цепочка PrintStarted → UpdateCounterFields → global map

## Результат

Для ветки `LocalPrintheadProtocol.this+0x524 & 0x400 == 0` путь от драйверного start до логического изменения счётчиков замкнут статическим ARM-кодом. Запрос обновления исходит из обработчика начала печати, а не из `PrintCompleted`. ImageMgr принимает его через observer, ставит событие, а отдельный поток вызывает CiffSelect с битом `IUF_COUNTERS=2`. CiffSelect переносит NextValue в CurrentValue и global map, затем запускает сохранение. Поэтому считать global counter14 исключительно счётчиком успешно завершённых физических отпечатков нельзя.

Путь асинхронный: этот вывод не задаёт абсолютный момент записи относительно механического конца — поток может выполнить работу позже. Не доказаны аппаратная долговечность RTC1: и возможная компенсация через внешние callback завершения/ошибки.

## Точная связь параметра с worker

В таблице `ImageMgr.dll:0x45712268` запись занимает 12 байт: `[groupID, namePointer, callbackID]`. Запись `0x457122f8` содержит group `0x1b`, имя `UpdateCounterFields`, callback ID `12` (`0x0c`). Инициализатор `0x456d59e0…0x456d59f0` передаёт таблицу в `0x456d3788`. Регистрация `0x456d13c4` передаёт ID через r3 в `0x456d12ac` (`0x456d14b4`), а последняя сохраняет его в записи словаря. Callback `0x456cf06c` получает этот ID через `0x456cef60`; чтение ID из записи находится в `0x456cf044`.

**Существенная поправка адресации this:** observer — отдельный COM-интерфейс по адресу `main+4`. Его IID `dfd07549-93d7-11d4-98b4-00b0d0665d37` получен QueryInterface в `0x456d5970…0x456d5980`; COM map `0x4570251c` содержит pointer на IID, а `0x45702520` содержит offset `4`. Дополнительное подтверждение — callback при вызове native-функции вычитает `4` из this (`0x456cf548`). Нельзя смешивать offset внутри observer и main object.

Callback ID12 попадает в `0x456cf1f0`: при event flags &2 читает handle `[observer+0x370c]` в `0x456cf200` и вызывает EventModify через общую ветку `0x456cf1b4`. Это **`main+0x3710`**.

Worker `0x456ecce4`:

| Элемент | ARM-доказательство |
|---|---|
| Читает handle `main+0x3710` | `0x456ecd34` |
| Сохраняет его в элементе таблицы `sp+0x7c` | `0x456ecd68` |
| Для того же элемента сохраняет обработчик `0x456eb1d4` в `sp+0x84` | `0x456ecdf0…0x456ecdf4` |

Handle `main+0x370c` относится к другому обработчику (`0x456ea698`, variable update). Ошибка на 4 байта здесь меняет семантику обновления: именно поэтому сохранены COM map и доказательство observer offset.

## Вызов CiffSelect с флагом COUNTERS

Обработчик `0x456eb1d4` использует `main+0x36dc = ICiffSelection`:

1. Читает `TimeUpdates` slot +0x24 (`0x456eb214`) и `CountUpdates` slot +0x28 (`0x456eb238`) для текущей линии. LineID=-1 преобразуется в0.
2. При успешных HRESULT и CountUpdates !=0 продолжает. Если `main+0x3794 ==0`, вызывает `0x456eaba0(main, TimeUpdates, 1)` в `0x456eb26c`.
3. `0x456eaba0` требует ненулевой updater `main+0x36d8` и активный flag byte `main+0x36fc`; далее вызывает updater slot +0x10 в `0x456eac20`. При `main+0x3794 !=0` вместо прямого вызова выставляются запросы очереди через `0x456e81ec` / `0x456e824c`; их полный runtime-порядок отдельно не установлен.

`main+0x36d8` создаётся как `ICiffUpdater`, IID `513d2d6a-f821-11d4-9589-00b0d03b2f2b`, создание `0x456e85d0…0x456e85ec`. В CiffSelect COM map и vtable связывают этот интерфейс с vtable `0x45939390`: slot +0x10 — `UpdateSynchronous`, реализация `0x4591d2e0`.

В `CiffSelect.dll:0x4591d2e0`:

- r2 (переданный TimeUpdates) сохраняется в r4 (`0x4591d2f0`);
- `ICiffSelection.UpdateFields` slot +0x18 берётся в `0x4591d364`;
- r3 устанавливается в **3**, если TimeUpdates !=0 (`0x4591d370`), иначе в **2** (`0x4591d378`);
- сам вызов — `0x4591d38c`.

Итак, обе ветки содержат bit2 COUNTERS. Это не вывод по имени enum: конкретные константы2/3 стоят непосредственно перед реальным виртуальным вызовом UpdateFields. Bit1 дополнительно разрешает время.

Дальнейший путь и точка commit описаны в `ciffselection_counter_ru.md`: `UpdateFieldsEx 0x4591bfc4` → `0x4591ae60` → проверка bit2 в `0x4591b034` → `0x4591984c` → второй проход `0x459181f0`; `NextValue.get` в `0x45918264`, `CurrentValue.put` в `0x4591829c`, global map update `0x45920ea0` в `0x459182f0`, dirty=1 в `0x45920ff8`. Если counter GlobalID=14, запись идёт в14. Настройки PrintsPerCount, ParentCounter, диапазона и rollover могут препятствовать обычному +1; одного start недостаточно для безусловного increment14.

## Пределы вывода

- Доказана обычная ветка `Imaging/UpdateCounterFields`; альтернативный LPP режим с `NextSyncUpdateReq` и очередь ImageMgr при `main+0x3794 !=0` нельзя автоматически приравнивать по временному порядку.
- Настройки конкретного экземпляра и живой CurrentCounts/RTC state в поставленном образе отсутствуют. Реальное текущее значение14 и выбранный runtime-режим этим кодом не восстановить.
- Начало цикла инициирует обновление; complete/abort происходят через отдельные callbacks. Для доказательства отсутствия компенсации после abort нужны реализации внешних callbacks либо стенд.
- Возврат отрицательного HRESULT не гарантирует rollback: snapshot вызывается до проверки результата в `UpdateFieldsEx` (`0x4591c17c`).

Сохранённый компактный native-листинг: `ImageMgr_counter_binding_evidence.asm`; изменения в физических обработчиках и эмуляция: `print_cycle_ru.md`, `verify_cycle_native.py`, `native_cycle_results.json`.

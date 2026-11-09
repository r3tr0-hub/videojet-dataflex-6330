# CIFF: связь счётчиков, текущие и следующие значения

Разбор поставленного `CiffMgr.dll`; ARM VA относятся к образу с базой `0x457d0000`. SHA-256: `b7622659aedff652e3567c28fd5e5bc1a21443902b722ceeeb6b65d5641031d4`.

Этот документ описывает нижний уровень объектов CIFF. Реализация менеджера и связь с началом цикла затем замкнуты в `ciffselection_counter_ru.md` и `ImageMgr_counter_binding_ru.md`; их текущий итог собран в `COUNTERS_FINAL_RU.md`.

## Подтверждённые интерфейсы

Имена методов взяты из встроенной type library, но фактическая реализация проверена по vtable и ARM. `ICiffDataObject` IID `775bf6b3-5d5c-432b-8c67-5cb2b40ebc66` имеет vtable `0x4581c768`; `ICiffSubCounter` IID `b70a962e-fb25-4911-b19a-fa701d774238` — vtable `0x4581bba8`.

| Свойство | Слот get / put | ARM get / put | Поле объекта |
|---|---|---|---|
| ICiffDataObject.Rollover | +0xfc / +0x100 | 0x457d551c / 0x457d556c | +0xd4, 0 или 1 |
| PrintsPerCount | +0x104 / +0x108 | 0x457d55bc / 0x457d560c | +0xdc; put также записывает +0xe0 |
| ResetOnSelect | +0x10c / +0x110 | 0x457d56f8 / 0x457d5748 | +0xe4, 0…2 |
| ParentCounter | +0x114 / +0x118 | 0x457d640c / 0x457d6464 | +0xf0, копия BSTR |
| PrintsThisCount | +0x11c / +0x120 | 0x457d565c / 0x457d56ac | +0xe0, >=0 |
| ICiffSubCounter.CurrentValue | +0x54 / +0x58 | 0x457e2d18 / 0x457e2d5c | +0x3c, отдельный BSTR |
| NextValue | +0x84 / +0x88 | 0x457e2d8c / 0x457e2dd0 | +0x40, отдельный BSTR |
| Global | +0x90 / +0x94 | 0x457e2ad8 / 0x457e2b10 | +0x5c, 0 или 1 |
| GlobalID | +0x98 / +0x9c | 0x457e2b48 / 0x457e2b80 | +0x60, -1…15 |

`PrintsPerCount.put` требует строго положительное значение и одновременно устанавливает `PrintsThisCount` тем же значением (`0x457d5640`, `0x457d5644`). Это факт инициализации остатка/фазы счёта; само по себе не доказывает, на каком физическом событии его уменьшают.

`ParentCounter` доступен при `DataType==5`; иначе методы возвращают `0x80070005`. Сеттер лишь копирует строку под critical section. Он не ищет другой счётчик и не выполняет increment, файл или registry write. В XML reader `0x457fb2ec` берёт имя `ParentCounter` из таблицы `0x4582df28+0x158`, получает текст и передаёт его в slot +0x118 при `0x457fb348`.

## CurrentValue и NextValue — два самостоятельных поля

`CurrentValue.put` копирует BSTR в +0x3c. `NextValue.put` копирует BSTR в +0x40. Ни один из этих двух методов не присваивает второе поле и не выполняет арифметику. Поэтому нельзя по одному наличию `NextValue` назвать его атомарной фиксацией физической печати.

CIFF reader обрабатывает XML `CurrVal` как tag index `0x5c` и вызывает `ICiffSubCounter.CurrentValue.put +0x58` в `0x457f074c`. Writer читает `CurrentValue.get +0x54` в `0x4580282c` и, если BSTR непустой, пишет `CurrVal` (`0x4580284c`, `0x45802858`). Так доказана возможность сохранения текущего значения в CIFF. Частота, момент и crash-safety записи этим участком не устанавливаются. Сохранённый CIFF не следует считать журналом успешно нанесённых кодов.

При чтении `SubCnt` глобальность устанавливается отдельно: `0x457f51c4` вызывает `Global.put`; `0x457f51d8` вызывает `GlobalID.put`. Преобразование `0x45811dac` сравнивает строковые ID по таблице `0x4582e6e0`: `Line` соответствует -1, `0`…`15` соответствуют 0…15. Таким образом, global ID 14 — штатное допустимое значение; он не получается из `ParentCounter`.

## Точка передачи manager в DataFile

Для продолжения трассы global counter найден интерфейс `38a16253-14bf-483d-9653-3a8dec06e38d`. `ImageMgr.dll:0x456c4f70` сравнивает IID по литералу `0x456fd9d4`, затем `0x456c4fa0` передаёт этот интерфейс в DataFile object+8. Именно у него DataFile вызывает slot +0x50 с r1=14 (`0x456c4af4`, `0x456c4d20`). IID присутствует в ProjectMachineControl, CiffSelect, MkmCimComms, DatabaseManager, ZBC2, CLARiTYHMI. Реализацию slot+0x50 в этом отчёте не присваиваем по догадке.

## Граница вывода

CiffMgr даёт точную схему объектов и пути XML read/write. Здесь не доказаны commit после печати, восстановление после питания, rollback после abort и защита от повторного кода. Эти свойства следует выводить из manager/print state paths, а не из имён enum. Подтверждающие ARM-фрагменты: `ciff_counter_evidence.asm`.

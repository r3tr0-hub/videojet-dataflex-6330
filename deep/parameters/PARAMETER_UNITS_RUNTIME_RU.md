# Параметры Videojet 6330: единицы, масштаб, UI и runtime

Статический разбор образа `microSD 409720r12SP5`, продукт 31. Сетевые обращения и изменения принтера не выполнялись. Исходные отчёты не изменены.

Получен объединённый каталог **897 уникальных путей**, включая **295 сохранённых параметров** и **602 пути, отсутствующие в сохранённом снимке**. Это полный результат объединения перечисленных ниже источников, **не доказательство полноты живого Information Manager**. Слово `runtime_only_candidate` означает только отсутствие в снимке: в этой группе также находятся условные функции, команды, контекстные пути и шаблоны ведомых принтеров. Ни один такой путь не объявлен подтверждённым live-readback.

| Источник | Уникальных путей | Что доказывает |
|---|---:|---|
| Params.1/2/3.xml и прежний очищенный latest-каталог | 295 | сохранённые значения, типы, flags, диапазоны и некоторые numType/stateType |
| UIConfig.xml | 480 | привязку к экрану, условия видимости, readOnly, userLvl, UI-default/min |
| RemoteServiceControl.xml / ParameterParams | 314 | подписку сервиса: MsgID, DataTag, Time, Delta, EvtID |
| MachineControl.xml / Parameters | 150 | определения параметров машины, включая несохраняемые объекты |
| AvailabilityConfig.xml / SnapshotParams | 12 | состав снимка диагностики и его конфигурационные min/max |
| QRSupportTicket.xml / CalcData | 56 | наличие ссылок на пути без доказанного типа |
| ProjectPlatformDriver.dll | 1 | нативное определение температуры платы, отсутствующее в Params |

Пересечения источников сохранены; суммы строк не складываются в 897. Даты Params: `.1` — 27.02.2026 14:45, `.2` — 14:46, `.3` — 14:45. Это копии сохранённой конфигурации, не измерения 05.11.2026.

## Точные масштабы

В `CLARiTYHMI.exe` найдена таблица **53 числовых форматов**, VA `0x00294c58`, шаг `0x1c`. Поиск `0x0015eecc` ограничен 53 записями. Запись хранит имя, адрес formatter, число метрических десятичных знаков, функцию единиц, функцию imperial-conversion, число imperial-знаков и функцию imperial-единиц. Полный реестр — `numeric_format_registry.json`.

Для **62 записей каталога** формат позволяет привязать числовое значение к единице. Отсутствие `numType` оставлено неизвестностью, даже если имя похоже на температуру или скорость.

| numType | XML/raw → метрическое значение | Пример |
|---|---|---|
| NumTenthsmm | raw / 10 мм | 350 → 35,0 мм |
| NumHmm | raw / 100 мм | 5000 → 50,00 мм |
| NumMillimetres | raw мм | 55 → 55 мм |
| NumSpeed | raw мм/с | 380 → 380 мм/с |
| NumMs | raw мс | 100 → 100 мс |
| NumPercent | raw % | 100 → 100% |
| Num0.1Percent | raw / 10 % | 1000 → 100,0% |
| Num0.1KG | raw / 10 кг, как названо в HMI | PrintForce=22 → 2,2 кг; автоматического перевода в Н нет |
| Num0.1C | raw / 10 °C | 250 → 25,0 °C |

Масштаб относится к числам current/min/max/interval/def одинаково. В JSON имеются и исходные поля, и `engineering_values`. Для специальных форматов `PasswordMask`, `ShiftCodes`, `StartOfDay`, `AsyncNotificationsEnabled`, `NumInputConfigZPP`, `NumOutputConfigNPP` обычная физическая единица не назначается.

Основные подтверждённые настройки из сохранённого снимка:

| Путь относительно Devices/PHds/1/ | Сохранённое raw | Физическое значение | Диапазон определения |
|---|---:|---:|---|
| PrintInformation/PrintSpeed | 380 | 380 мм/с | 10…750 мм/с, interval 5 |
| PrintInformation/ContinuousMaximumPrintSpeed | 750 | 750 мм/с | 100…750 мм/с, interval 5 |
| PrintInformation/ContinuousPrintPosition 0_01mm | 5000 | 50,00 мм | 0…76,50 мм, interval 0,10 мм |
| PrintInformation/IntermittentPrintRegistrationTmm | 350 | 35,0 мм | 0…65,0 мм |
| PrintInformation/VerticalRegistrationTmm | 45 | 4,5 мм | −53…53 мм, interval 0,5 мм |
| Consumables/RibbonWidth | 55 | 55 мм | 20…55 мм |
| Consumables/RadialRibbonWidthLimit | 55 | 55 мм | 5…55 мм |
| IAssure/RejectDelay | 100 | 100 мс | 0…5000 мс |

### Дюймы и скорость imperial

Выбор HMI хранится в `UserInterfaces/CLARiTY/MeasurementUnits`: 0=Metric, 1=Inches. Функция `0x00160310` возвращает метрический режим, кроме успешного чтения значения 1. Это настройка представления HMI; XML значения остаются raw.

Реальное ARM-исполнение подтверждает:

- mm→in: `x * 0.03937007933143675`; in→mm: `x * 25.399999618530273` (`0x0015ef20`).
- mm/s→ft/min: `x * 0.1968500018119812`; обратная ветвь: `x * 5.080010113259422` (`0x0015f108`).
- Общая конверсия `0x0015f220` делит raw на `10^metricDecimals`, переводит единицу, округляет до `imperialDecimals`, умножает на `10^imperialDecimals` и приводит к целому. Обратный путь — `0x0015f34c`.
- Для длины imperialDecimals=3. Поэтому raw254 формата NumTenthsmm преобразуется в UI-целое1000, то есть 1,000 in; NumHmm raw2540 — в то же UI-целое.
- `0x0015ed50` округляет половины от нуля: 1,2345→1,235 и −1,2345→−1,235 при трёх знаках.

**Обнаружено несоответствие температурной обратной ветви.** `0x0015f024` правильно вычисляет C→F как `1.8*C+32`, но при direction=0 вычисляет `(F−32)*1.8`. Исполнение ARM даёт 77°F→81°C. В общем пути HMI raw250→imperial770, а обратное imperial770→raw810. Это подтверждённое поведение конкретной функции конкретной сборки; полный UI не исполнялся, доступность её редактируемых температурных полей не утверждается. В SCADA следует хранить raw/°C и использовать математическое `(F−32)/1.8` для собственного представления, не копировать ошибочную ветвь.

Дополнительное статическое несоответствие реестра: `NumTenThoumm` имеет metricDecimals=4, но его formatter `0x00161520` использует literal 0.001. Общая функция использует 4; графическое отображение этим formatter может отличаться в 10 раз. В сохранённых 295 параметрах этот numType не используется. Полный formatter не эмулировался.

## XML Num — целое в тексте узла

Нативный parser `ProjectInformationManager.dll:0x4442adb8` вручную читает UTF-16: необязательный знак и последовательность цифр; прекращает на первом другом символе. Пробелы не пропускает. Эмуляция настоящих инструкций:

| Входной текст Num | Результат parser |
|---|---:|
| `5000` | 5000 |
| `50.00` | 50 |
| `-10.9` | −10 |
| ` 500` | 0 |
| `+0012` | 12 |
| `12mm` | 12 |

Для 50,00 мм при NumHmm необходимо отправить **`5000`**, не `50.00`. Число передаётся текстом узла `<Num id="…">5000</Num>`. Приведённое permissive-поведение parser не является рекомендацией посылать суффиксы: генератор SCADA должен выдавать строгую десятичную целую строку.

## Температуры и runtime

Нативное определение `Platform/Inputs/PCBTemperature` восстановлено из `ProjectPlatformDriver.dll`:

- descriptor `0x44563470`: type=2 (Num), class=100, имя PCBTemperature, flags=262, metadata=`0x44561e9c`;
- class100 соответствует `Platform/Inputs/` в таблице классов;
- metadata: min=−200, max=1000, initial/default=250, interval=0, numType=`Num0.1C`;
- подтверждённый диапазон определения −20…100°C, начальное значение 25°C, текущая температура **неизвестна**. flags262 не проходит XML-gate изменения существующего значения.

`Devices/PHds/1/Inputs/PrintheadTemperature` есть в UI, сервисе и AvailabilityConfig, но его живой `numType` в этих источниках отсутствует. Диагностический диапазон −200…1000 сам по себе не доказывает масштаб 0,1°C. Аналогично оставлены неподтверждёнными масштабы runtime ribbon-диаметров, LineSpeed/Encoder/PrintSpeed, накопительных расстояний и performance-speed/throughput, когда нет привязанного определения. Не следует переносить numType соседней сохранённой настройки на runtime датчик по похожему имени.

Для Performance, Consumables/Ribbon и iAssure каталог содержит все пути объединяемых источников, сервисные MsgID/DataTag, UI readOnly/userLvl/visible и отдельно факт отсутствия сохранённого current. Например, `Consumables/Ribbon/Percentage` остаётся без физического масштаба, несмотря на слово Percentage. Данные мониторинга сервиса задают подписку, а не разрешение записи и не параметры универсального протокольного запроса.

## UI, enum и прошивка — отдельные ограничения

- PrintDarkness: сохранённое определение 0…100; UIConfig задаёт дополнительный `min="50"`. В каталоге это два разных поля.
- RibbonWidth: сохранённые max/default=55; UI содержит условные default=33/55/110 для разных PrintheadWidth. Значение110 не объявлено допустимым для этого сохранённого 55-мм определения.
- BaudRate: языковой enum содержит индексы0…14, но сохранённый max=12. `enum_allowed_by_saved_range` оставляет0…12; индекс12=115200. Наличие перевода для индекса не расширяет фактический диапазон.
- iAssureAutomaticVerticalPrintRegistration: 0=Off, 1=Move if Off Ribbon, 2=Centre of Ribbon. В некоторых UI-привязках поле readOnly при `IAssureOverridesVerticalRegistration=1`; условия сохранены буквально.
- UI userLvl и readOnly относятся к экрану. Они не становятся сетевыми правами пользователя.

Проверка flags для XML изменения существующего значения сохранена из предыдущего нативного разбора: `(flags & 0x120)==0 && (flags & 0x200)==0x200`. Из метаданных каталога её проходят 158 записей, 255 не проходят, у 484 нет достаточных metadata-flags. Это **не числа гарантированно доступных сетевых параметров**: живые flags, объект, сессия и обработчики могут отличаться.

Num-setter дополнительно проверяет min/max; при выходе за диапазон оставляет current и возвращает S_OK. Наличие interval в метаданных не означает его проверки примитивным setter. Подтверждать результат нужно readback отдельного узла, не одним ACK.

## Контекстные классы MachineControl

В `ProjectMachineControl.dll` таблица классов начинается с `0x455dcb38`, содержит **265** записей по16байт; `0x455b4c4c` возвращает адрес и count=0x109. Извлечены class_id, имя PRMCLS, mode и prefix. В `machinecontrol_class_prefixes.json` сохранён весь реестр.

Resolver `0x455a4d4c` для mode!=0 при наличии device-контекста добавляет этот контекст перед prefix. Поэтому PRMCLS_DEVCOMMS→`Communications/` оставлен в каталоге как **`$DEVICE_CONTEXT/Communications/…`**, а не выдан за глобальный абсолютный путь. Подстановка фактического device-контекста требует живой сессии либо независимо подтверждённой конфигурации вызывающего компонента.

## Файлы и воспроизведение

- `merged_parameter_catalog.json` — все значения/диапазоны/flags, источники, enum EN/RU, условия UI, сервисные теги и evidence; пароли удалены.
- `merged_parameter_catalog.csv` — плоская выгрузка основных полей; вложенные структуры представлены JSON в ячейках.
- `numeric_format_registry.json` — 53 нативных формата; необъяснённые специальные типы оставлены без назначенной единицы.
- `machinecontrol_class_prefixes.json` — 265 классов.
- `numeric_native_evidence.arm.txt` — адресный листинг основных конверсий, parser и class-resolver.
- `numeric_conversion_tests.json` — **23** проверки с исполнением реальных ARM-инструкций:8 арифметических,8 generic UI-conversion,7 parser. Заменены только импортируемые функции OS math, не логика исследуемых функций.
- `catalog_tests.log` — **11** проверок целостности и разделения доказательств, включая runtime-неизвестности, UI min, enum bounds, нативную температуру платы и условные defaults.

Запуск из корня распакованного комплекта; pefile/unicorn должны быть установлены в используемый Python или доступны через PYTHONPATH:

```bash
python deep/parameters/build_catalog.py --source /path/to/original/CLARiTY --prior data/parameters_latest_saved.json --out /path/to/new/catalog
python deep/parameters/verify_numeric_conversions.py --bin-root /path/to/original/CLARiTY/BIN --output numeric_conversion_tests.json
python -m unittest discover -s deep/parameters -p 'test_catalog.py' -v
```

SHA-256 всех XML-источников и исследуемых native-binary находятся в JSON. Скрипт ARM-тестов отклоняет отличающийся hash HMI/InformationManager. Проверки полностью offline и не исполняют COM/MSXML-сессию, полный UI, аппаратные обработчики или физический принтер.

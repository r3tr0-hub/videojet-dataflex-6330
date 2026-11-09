# Удалённое перечисление архивов iAssure

Узкий дополнительный разбор закрыл найденный ранее пробел: архивы перечисляются через **DirectoryListing, filetype7, flags0x800**. Запрос filetype18 сам по себе получает конкретный файл и не перечисляет ID. Новый код не подключался к оборудованию; результаты ниже получены из ARM-кода прошивки 409720.r12.SP5 и изолированной эмуляции его сериализатора.

## Запрос

Native API `IZBC2MasterSession.RequestDirectoryListing(filename, flags, subDirectory, monitor, messageId)` соответствует реализации ZBC2 **446E3A4C**. Она выбирает FRQ5003/FRU5032 и filetype7. При непустом указателе subDirectory используется сериализатор **446DAD18**, сигнатура `(this, filenameWstr, flags32, subDirectoryWstr)`. Пустая строка — допустимый ненулевой указатель. При нулевом указателе subDirectory записывается только u32 flags после имени.

Обработчик **446BFD08**, ветвь filetype7 по **446BFE98**, вызывает генератор DirectoryListing.xml. Функция **446BEED4**, адрес **446BF27C**, проверяет флаг 0x800. В этой ветви она задаёт:

| Расширение | Тип файла в листинге |
|---|---:|
|.bmp|18|
|.erb|19|
|.txt|20|

По **446BF338** выбирается папка `IAssure` из коллекции `Folders`. Это прямое доказательство назначения флага 0x800. У этой функции есть последовательность проверок других флагов до 0x800; для получения именно iAssure следует использовать 0x800 без добавления других категорий.

Полные внутренние сообщения с пустыми filename и subDirectory получены **реальным сериализатором 446DAD18** в Unicorn и сохранены в `native_directory_request_fixtures.json`:

```text
FRQ5003, 16 байт:
03 50 10 00 00 00 07 00 00 00 00 08 00 00 00 00

FRU5032, 20 байт:
32 50 14 00 00 00 07 00 00 00 00 00 00 08 00 00 00 00 00 00
```

| Поле | FRQ5003 | FRU5032 |
|---|---:|---:|
|u16 opcode|0|0|
|u32 total|2|2|
|u16 filetype=7|6|6|
|пустой filename, counted string|8:u16(0)|8:u32(0)|
|u32 flags=0x800|10|12|
|пустой subDirectory, counted string|14:u16(0)|16:u32(0)|

Вместо расширения bitmap здесь расширение DirectoryListing. Парсер этого расширения — **446AB2D4**; базовый FRQ-парсер 446AB564 выбирает его через filetype7. Он читает u32 flags, затем counted subDirectory с соответствующей шириной длины.

Существующий стабильный `iassure_codec.py` не изменён. Его общий encoder позволяет собрать запрос без добавления нового специализированного API:

Дополнительно приложен отдельный `iassure_archive.py`: готовый `encode_iassure_directory_request` и разбор XML через `decode_iassure_directory`. `native_directory_oracle.py` повторно исполняет исходный сериализатор; `test_iassure_archive.py` сравнивает оба режима с native-фикстурами и проверяет синтетический UTF-16-листинг. Дата сохраняется буквально, неполные наборы файлов не дополняются догадками.

```python
import struct
from iassure_codec import encode_file_request
from zbc_codec import encode_text_field

unicode_mode = False
sub = '' if unicode_mode else b''
extra = struct.pack('<I', 0x800) + encode_text_field(sub, unicode_mode=unicode_mode)
request = encode_file_request(7, unicode_mode=unicode_mode, extra=extra)
```

`decode_file_request` в текущей версии намеренно не разбирает DirectoryListing-расширение и вернёт ошибку на таком запросе. Это не ограничивает encoder и не скрывается за успешной bitmap-проверкой.

## Ответ и записи

Результат — **обычный файловый ответ 5004 FTX** с filetype7 и именем `DirectoryListing.xml`; его обёртка уже описана в IASSURE_RU.md и разбирается `decode_file_transfer`. Разборщик транспорта должен сначала собрать полный ответ. Пустое имя запроса заменяется на DirectoryListing.xml по 446BFF60. Дальнейший путь отправки совпадает с обычным файловым ответом по 446C04B8–446C0538.

XML строится DOM-операциями, а не отдельной бинарной таблицей фиксированных записей:

- **446BE214** создаёт XML processing instruction с `encoding="UTF-16"` и корневой Folder.
- **446BD46C** перечисляет объекты папки и добавляет File.
- Таблица строк **4470EAC0** содержит Folder, File, Name, Type, Size, DateModified, LastDownloaded.
- По **446BDA08** создаётся File; по 446BDA80 задаётся Name; по 446BDAD8 задаётся Type как десятичное число типа 18/19/20.
- Size добавляется по 446BDB90, если flags&0x4000 не задан.
- DateModified добавляется по 446BDC08, если flags&0x8000 не задан. Форматтер по 44703398 — ASCII `%g`, то есть числовая строка даты, а не ISO8601. Часовой пояс и точная семантика этой даты данным узким проходом не установлены.
- LastDownloaded связан с дополнительной ветвью для type1/CIFF; его наличие у каждого iAssure-файла не предполагается.

Показательный вид записи, **не реальный полученный листинг принтера**:

```xml
<?xml version="1.0" encoding="UTF-16"?>
<Folder Name="">
  <File Name="0001.bmp" Type="18" Size="12345" DateModified="46000.5"/>
  <File Name="0001.erb" Type="19" Size="12345" DateModified="46000.5"/>
  <File Name="0001.txt" Type="20" Size="512" DateModified="46000.5"/>
</Folder>
```

Числа Size и DateModified здесь иллюстративные. Native XML не создаёт отдельный атрибут FailureID в показанном конструкторе. ID выводится из имени `%04d.ext`, заданного генератором архивных имён ProductNimitz45C06668. Нужно группировать совпадающие числовые основы имени и учитывать, что одна из трёх записей может отсутствовать. `.tru` данная ветвь списка не добавляет.

После снятия файловой обёртки содержимое можно читать стандартным XML-парсером, который учитывает UTF-16 declaration/BOM:

```python
import re
import xml.etree.ElementTree as ET
from iassure_codec import decode_file_transfer

# transferred = decode_file_transfer(reassembled_reply, unicode_mode=False)
# root = ET.fromstring(transferred.data)
# archive_records = []
# for node in root.iter('File'):
#     kind = int(node.attrib['Type'])
#     name = node.attrib['Name']
#     match = re.fullmatch(r'([0-9]+)\.(bmp|erb|txt)', name)
#     if kind in (18, 19, 20) and match:
#         archive_records.append((int(match[1]), kind, name))
```

Для последующего получения файла используется соответствующий type18/19/20 и **точное имя из списка**. Это лучше, чем угадывать непрерывный диапазон счётчиков. Синтаксис запроса и назначение флага теперь доказаны; реальный листинг, неполные архивные наборы, ошибки папки, конкурентная ротация файлов и получение нескольких сообщений по живому сеансу остаются стендовыми проверками.

Дополнительные адресованные извлечения: `evidence/ZBC2_directory_listing_XML.arm.txt`, `evidence/ZBC2_directory_listing_records.arm.txt`, `evidence/ZBC2_directory_file_records.arm.txt`. Стабильные кодеки и тестовые fixtures предыдущего дополнения не менялись.

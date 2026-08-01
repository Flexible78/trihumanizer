"""Server-side keyboard-layout validation.

Mirrors the core logic of ``static/layout-corrector.js`` for request-time
sanity checks. The browser module remains the source of truth for instant
client-side correction; this module lets the server detect and report likely
wrong-layout text without modifying it.

Supported: English QWERTY <-> Russian JCUKEN <-> Israeli Hebrew, via the
shared physical key positions.
"""
from __future__ import annotations

import re

RU_MAP = {
    "q": "й", "w": "ц", "e": "у", "r": "к", "t": "е", "y": "н", "u": "г",
    "i": "ш", "o": "щ", "p": "з", "[": "х", "]": "ъ",
    "a": "ф", "s": "ы", "d": "в", "f": "а", "g": "п", "h": "р", "j": "о",
    "k": "л", "l": "д", ";": "ж", "'": "э",
    "z": "я", "x": "ч", "c": "с", "v": "м", "b": "и", "n": "т", "m": "ь",
    ",": "б", ".": "ю",
}
HE_MAP = {
    "q": "/", "w": "'", "e": "ק", "r": "ר", "t": "א", "y": "ט", "u": "ו",
    "i": "ן", "o": "ם", "p": "פ", "[": "]", "]": "[",
    "a": "ש", "s": "ד", "d": "ג", "f": "כ", "g": "ע", "h": "י", "j": "ח",
    "k": "ל", "l": "ך", ";": "ף", "'": ",",
    "z": "ז", "x": "ס", "c": "ב", "v": "ה", "b": "נ", "n": "מ", "m": "צ",
    ",": "ת", ".": "ץ",
}

RU_TO_KEY = {char: key for key, char in RU_MAP.items()}
HE_TO_KEY = {char: key for key, char in HE_MAP.items()}

# Compact common-word dictionaries so correct text is never rewritten.
# (The browser module has richer lists; this mirror only needs the core set.)
EN_COMMON = set(
    """the be to of and a in that have i it for not on with he as you do at this but his
    by from they we say her she or an will my one all would there their what so up out if
    about who get which go me when make can like time no just him know take people into year
    your good some could them see other than then now look only come its over think also back
    after use two how our work first well way even new want because any these give day most us
    is are was were been being has had did does please thanks thank hello hi goodbye welcome
    sorry yes no okay fine great good bad nice wonderful beautiful happy sad angry tired
    hungry thirsty busy free ready done finished started stopped working waiting talking
    speaking writing reading listening watching looking feeling thinking knowing understanding
    helping asking answering telling saying giving taking making doing going coming seeing
    hearing living loving hating wanting needing using trying finding losing winning buying
    selling paying spending earning saving starting ending opening closing turning moving
    staying leaving arriving flying driving walking running jumping swimming singing dancing
    playing studying learning teaching training testing checking fixing repairing building
    creating designing developing programming coding debugging installing updating upgrading
    downloading uploading sending receiving sharing publishing posting commenting liking
    following subscribing connecting linking browsing searching saving deleting editing copying
    pasting cutting selecting choosing deciding planning organizing preparing scheduling
    meeting calling emailing messaging texting chatting translating interpreting explaining
    describing presenting reporting reviewing analyzing evaluating comparing contrasting
    summarizing concluding recommending suggesting asking clarifying confirming verifying
    approving rejecting accepting declining agreeing disagreeing discussing debating arguing
    negotiating cooperating collaborating coordinating communicating informing notifying
    warning advising encouraging motivating inspiring supporting assisting guiding leading
    managing directing supervising monitoring controlling operating maintaining replacing
    improving enhancing optimizing adjusting configuring customizing integrating restoring
    securing protecting encrypting hiding revealing publishing broadcasting streaming ordering
    purchasing returning exchanging refunding canceling booking reserving rescheduling
    delaying hurrying rushing waiting remaining departing traveling touring visiting exploring
    discovering finding seeking searching looking hunting chasing catching holding keeping
    storing saving preserving retaining containing including excluding adding removing erasing
    clearing emptying filling loading unloading packing unpacking building making producing
    manufacturing constructing assembling fitting cleaning washing drying ironing folding
    cooking baking boiling frying roasting grilling preparing serving eating drinking tasting
    enjoying appreciating valuing respecting admiring praising apologizing forgiving tolerating
    permitting allowing forbidding prohibiting preventing stopping blocking banning restricting
    limiting reducing increasing growing expanding extending shrinking decreasing declining
    falling rising improving worsening changing altering modifying transforming converting
    adapting substituting swapping exchanging trading selling requesting demanding requiring
    needing wanting wishing hoping desiring dreaming imagining visualizing arranging handling
    dealing coping solving resolving settling finishing completing accomplishing achieving
    succeeding failing attempting practicing researching investigating examining inspecting
    analyzing assessing evaluating judging rating scoring grading ranking comparing matching
    pairing grouping sorting classifying categorizing labeling tagging naming identifying
    recognizing remembering recalling forgetting memorizing noting recording documenting
    logging tracking monitoring observing highlighting emphasizing quoting citing referencing
    sourcing attributing crediting acknowledging congratulating celebrating honoring rewarding
    compensating reimbursing repaying settling clearing reconciling auditing validating
    certifying endorsing funding investing financing sponsoring donating contributing
    volunteering aiding nursing caring tending nurturing raising feeding clothing sheltering
    housing accommodating welcoming hosting entertaining amusing delighting pleasing
    satisfying fulfilling meeting exceeding surpassing outperforming beating defeating
    conquering overcoming excelling thriving prospering flourishing blooming developing
    maturing aging progressing evolving adapting growing becoming turning concentrating
    focusing centering targeting aiming directing stressing underscoring exaggerating
    minimizing downplaying softening tempering moderating easing relaxing loosening tightening
    strengthening weakening adding subtracting multiplying dividing counting calculating
    computing measuring weighing quantifying estimating approximating guessing assuming
    supposing presuming hypothesizing theorizing speculating wondering pondering contemplating
    meditating reflecting deliberating considering balancing determining resolving settling
    store support glasses hours stock email phone address model order exchange return available
    optical customer service opening closed open monday tuesday wednesday thursday friday
    saturday sunday week month year today tomorrow yesterday morning evening afternoon night
    price cost discount delivery shipping contact question answer request please""".split()
)

RU_COMMON = set(
    """и в во    не на я ты вы мы он она оно они это тот эта эти как так что чтобы если же
    только привет здравствуйте пока спасибо пожалуйста извините да нет хорошо плохо очень
    твои твой твоя твоё дела дело дел твоих
    много мало можно нельзя нужно хочу могу будет есть был была были быть делать сделал
    сделала делаю сказать сказал говорит сказала говорить понимаю понял поняла знаю знал
    знала вижу видел слышу слышал писать написал написала пишешь читать прочитал читаю
    перевести переводить перевод перевожу текст языка язык языки русский английский иврит
    переводчик работа работаю работает работать работал дом дома город магазин письмо
    сообщение позвонить звонить телефон времени время сейчас сегодня завтра вчера день
    ночь утро вечер человек люди друг подруга семья мама папа брат сестра дети ребёнок
    вопрос ответ спросить отвечать ответить помочь помощь просить прошу хотеть люблю
    нравится думать думаю подумать решить решил значит конечно может быть наверное точно
    правда согласен согласна против вместе всегда никогда иногда часто редко быстро
    медленно отлично ужасно нормально также ещё уже больше меньше лучше хуже новый старая
    старый молодой большой маленький длинный короткий высокий низкий дорогой дешёвый
    хороший интересный скучный сложный простой важный срочно потом раньше позже около
    почти совсем деньги цена цены стоить стоит купить покупать продавать продать заказ
    заказать доставка адрес улица номер квартира двери дверь открыть закрыть включить
    выключить начать начал начала закончить закончил продолжать готово проверить проверка
    тест тесты ошибка ошибки проблема проблемы решено исправить исправил версия версии
    обновить установить скачать загрузить отправить отправлять получить получать прислать
    пришлите отправьте прочитайте напишите позвоните приходите приходи приезжайте приезжай
    уходите стой остановитесь подожди подождите извините простите большое огромное сердечное
    благодарю благодарность добрый день доброе утро добрый вечер спокойной ночи до свидания
    до встречи удачи успехов всего хорошего всего доброго пожелания уважением искренне ваш
    твоя мой моё мои наши ваш ваша ваше ваши их его её нам вас тебе себе меня обращение
    просьба извинение вопрос совет рекомендация задача цель результат итог вывод решение
    план действия шаги этапы пункты список отчёт документ документы файл папка программа
    приложение система сервер клиент компьютер ноутбук телефон планшет экран клавиатура
    мышь интернет браузер страница сайт ссылка ссылки логин пароль аккаунт профиль
    настройки настройка параметры опции режим режимы функция функции возможность возможности
    скорость качество количество дата место расстояние направление маршрут билет билеты
    поезд самолёт аэропорт вокзал станция остановка автобус метро такси машина автомобиль
    дорога перекрёсток пешеход светофор правило правила закон законы права обязанности
    ответственность здоровье болезнь врач больница аптека лекарство таблетка рецепт лечение
    доктор медсестра операция анализ обследование приём запись очередь расписание график
    учёба школа университет институт колледж курс курсы занятие урок домашнее задание
    экзамен оценка балл учитель преподаватель студент студентка группа класс отпуск
    выходной праздник каникулы командировка поездка путешествие отдых развлечение кино
    театр музей выставка концерт спектакль день рождения новый год рождество пасха свадьба
    юбилей вечеринка встреча свидание знакомство дружба отношения чувства эмоции настроение
    радость счастье грусть печаль страх тревога волнение надежда вера уверенность сомнение
    решимость мужество смелость терпение настойчивость цель амбиция мотивация вдохновение
    творчество искусство культура наука технология инновация открытие исследование
    эксперимент гипотеза теория практика опыт навык умение знание компетенция квалификация
    стаж резюме собеседование вакансия должность зарплата оклад премия бонус страхование
    пенсия налог налоги финансы инвестиции капитал прибыль убыток доход расход бюджет
    планирование стратегия менеджмент управление руководство сотрудник коллега начальник
    директор менеджер специалист эксперт консультант партнёр клиент поставщик подрядчик
    контракт договор соглашение сделка переговоры обсуждение совещание переписка звонок
    звонки чат форум блог статья заметка новость новости пресса журнал газета публикация
    реклама маркетинг бренд продукт услуга сервис качество гарантия возврат обмен ремонт
    установка настройка конфигурация интеграция совместимость лицензия ключ активация
    регистрация запись пароль безопасность защита шифрование конфиденциальность политика
    правила условия приложение платформа инструмент средство способ метод подход модель
    структура процесс процедура регламент стандарт норматив требование условие критерий
    показатель индикатор метрика статистика данные информация сведения факты источники
    ссылки доказательства подтверждение опровержение аргумент дискуссия спор обсуждение
    мнение точка зрения позиция подход взгляд убеждение принцип ценность приоритет миссия
    видение стратегия тактика график срок дедлайн этап фаза стадия шаг пункт раздел глава
    параграф приложение комментарий примечание сноска цитата выдержка отрывок фрагмент
    кусок часть целое полный частичный краткий подробный детальный общий частный конкретный
    абстрактный""".split()
)

HE_COMMON = set(
    """שלום מה שלומך תודה בבקשה סליחה מצטער כן לא טוב רע יפה נהדר נפלא מדהים שמח עצוב
    כועס עייף רעב צמא עסוק פנוי מוכן גמור סיים התחיל עבד עובד מחכה מדבר כותב קורא מקשיב
    מסתכל מרגיש חושב יודע מבין עוזר שואל עונה אומר מספר נותן לוקח עושה בא הולך רואה שומע
    נוגע טועם מריח אוהב שונא רוצה צריך מנסה מוצא מפסיד מנצח קונה מוכר משלם עולה מרוויח
    מוציא חוסך מתחיל מסיים פותח סוגר זז נשאר עוזב מגיע טס נוהג רץ קופץ שוחה שר רוקד משחק
    עובד לומד מלמד מתאמן בודק מתקן בונה יוצר מפתח מתכנת מתקין מעדכן מוריד מעלה שולח
    מקבל משתף מפרסם מגיב אוהב עוקב מתחבר מקשר מחפש שומר מוחק עורך מעתיק מדביק חותך בוחר
    מחליט מתכנן מארגן מכין קובע נפגש מתקשר הודעה מדבר כותב מתרגם מפרש מסביר מציג מדווח
    סוקר מנתח משווה מעריך מסכם ממליץ מציע שואל מברר מאשר מאמת בודק מסכים דוחה מקבל מסרב
    מתווכח דן מתלבט משתף פעולה מתאם מעדכן מודיע מזהיר מייעץ מעודד מניע תומך עוזר מנחה
    מוביל מנהל מכוון מפקח שולט מפעיל מריץ מתחזק משרת מתקן מחליף משדרג משפר מייעל מתאים
    מגדיר מתחבר משלב מסנכרן מגבה משחזר מאבטח מגן מצפין מסתיר חושף מפרסם משדר מזרים
    מסנכרן שומר מזמין קונה מחזיר מחליף מבטל דוחה מזרז מעכב ממהר נשאר עוזב יוצא מגיע נוחת
    ממריא נוסע מטייל מבקר מגלה תופס מאחסן מכיל כולל מוציא מוסיף מסיר מוחק מנקה ממלא
    מרוקן טוען פורק אורז מייצר מרכיב מתאים מטגן צולה מגיש אוכל שותה טועם נהנה מעריך
    מכבד מעריץ משבח מודה מתנצל סולח מבין מקבל סובל מרשה אוסר מונע עוצר חוסם מגביל
    מצמצם מגדיל מקטין נופל משתפר מחמיר משנה הופך מתפתח גדל מתקדם מבקש דורש מקווה חולם
    מדמיין מארגן קובע מתאם מטפל פותר מסיים משלים משיג מצליח נכשל מנסה מתרגל חוקר בודק
    מעריך שופט מדרג משווה תואם מקשר מקבץ ממיין מסווג מתייג שם מזהה מכיר זוכר שוכח מציין
    מתעד רושם עוקב צופה בוחן מסכם מדגיש מצטט מייחס נותן קרדיט מתחרט מברך מנציח מכיר
    מתגמל מפצה מחזיר משלם מסדר מאשר תומך מממן תורם מתנדב מסייע מקיים משמר מגן מאבטח
    מחזק משדרג מחדש משקם בונה מחדש מרפא מטפל מטפח מאכיל מלביש מחסה מארח מבדר משמח משביע
    עונה עוקף מתגבר בולט משגשג פורח גדל מזדקן משתנה ממזער מרכך מחליש מוסיף מחסיר מכפיל
    מחלק סופר מחשב מודד שוקל מנחש מניח משער מהרהר שוקל קובע מסיים פותר""".split()
)

_COMMON_BY_SCRIPT = {"en": EN_COMMON, "ru": RU_COMMON, "he": HE_COMMON}

CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")
HEBREW = re.compile(r"[\u0590-\u05ff]")
LATIN = re.compile(r"[a-zA-Z]")

PROTECTED_PATTERNS = [
    re.compile(r"https?://\S+", re.I),
    re.compile(r"www\.\S+", re.I),
    re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I),
    re.compile(r"(?:^|\s)[a-z]:[\\/]\S+", re.I),
    re.compile(r"(?:^|\s)[\\/]\S*", re.I),
    re.compile(r"(?:^|\s)v?\d+\.\d+(?:\.\d+)?\S*", re.I),
    re.compile(r"#[a-z0-9_]+", re.I),
    re.compile(r"@[a-z0-9_]+", re.I),
    re.compile(r"(?:ctrl|cmd|alt|shift|fn)\s*\+\s*[a-z0-9]+", re.I),
    re.compile(r"api[_.-][a-z0-9_.-]+", re.I),
    re.compile(r"[\w.-]+\s*=\s*\S+", re.I),
]


def _script(word: str) -> str | None:
    cyr = len(CYRILLIC.findall(word))
    heb = len(HEBREW.findall(word))
    lat = len(LATIN.findall(word))
    total = cyr + heb + lat
    if total == 0:
        return None
    if cyr / total > 0.85:
        return "ru"
    if heb / total > 0.85:
        return "he"
    if lat / total > 0.85:
        return "en"
    return None


def _convert(word: str, char_to_key: dict[str, str] | None, key_to_char: dict[str, str] | None) -> str:
    out: list[str] = []
    for ch in word:
        lower = ch.lower()
        converted: str | None = None
        if char_to_key:
            key = char_to_key.get(lower)
            if key:
                converted = key_to_char.get(key, lower) if key_to_char else key
        elif key_to_char and lower in key_to_char:
            converted = key_to_char[lower]
        out.append(converted or ch)
    return "".join(out)


def candidates(word: str) -> list[dict[str, str]]:
    script = _script(word)
    if script == "en":
        return [
            {"lang": "ru", "text": _convert(word, None, RU_MAP)},
            {"lang": "he", "text": _convert(word, None, HE_MAP)},
        ]
    if script == "ru":
        return [
            {"lang": "en", "text": _convert(word, RU_TO_KEY, None)},
            {"lang": "he", "text": _convert(word, RU_TO_KEY, HE_MAP)},
        ]
    if script == "he":
        return [
            {"lang": "en", "text": _convert(word, HE_TO_KEY, None)},
            {"lang": "ru", "text": _convert(word, HE_TO_KEY, RU_MAP)},
        ]
    return []


def _protected_spans(text: str) -> list[tuple[int, int]]:
    """Return [start, end) spans of protected regions in the text."""
    spans: list[tuple[int, int]] = []
    for pattern in PROTECTED_PATTERNS:
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end()))
    for match in re.finditer(r"\b\d+(?:[.,]\d+)*\b", text):
        spans.append((match.start(), match.end()))
    return spans


def _protected(word: str, start: int, spans: list[tuple[int, int]]) -> bool:
    end = start + len(word)
    return any(s < end and e > start for s, e in spans) or bool(re.search(r"\d", word))


def _words(text: str) -> list[str]:
    return re.findall(r"[\u0590-\u05ff\u0400-\u04ffa-zA-Z]+(?:['’-][\u0590-\u05ff\u0400-\u04ffa-zA-Z]+)*", text)


def _known_word(word: str) -> bool:
    """True when the word is a common word in its own script."""
    script = _script(word)
    if not script:
        return False
    return word.casefold() in _COMMON_BY_SCRIPT.get(script, set())


def validate_layout(text: str, source_language: str = "auto") -> dict:
    """Return a report describing likely wrong-layout text.

    Result: {likely_wrong_layout: bool, corrected: str, words_changed: int,
             total_words: int, confidence: float}
    """
    if not text or not text.strip():
        return {
            "likely_wrong_layout": False,
            "corrected": text,
            "words_changed": 0,
            "total_words": 0,
            "confidence": 0.0,
        }

    words = [(match.group(0), match.start()) for match in re.finditer(
        r"[\u0590-\u05ff\u0400-\u04ffa-zA-Z]+(?:['’-][\u0590-\u05ff\u0400-\u04ffa-zA-Z]+)*", text
    )]
    spans = _protected_spans(text)
    changed = 0
    corrected_words: list[str] = []
    for word, start in words:
        if _protected(word, start, spans):
            corrected_words.append(word)
            continue
        script = _script(word)
        if not script:
            corrected_words.append(word)
            continue
        # Never rewrite words that are already common in their own script.
        if _known_word(word):
            corrected_words.append(word)
            continue
        best: dict[str, str] | None = None
        for candidate in candidates(word):
            if not candidate["text"] or candidate["text"] == word:
                continue
            target_script = _script(candidate["text"])
            # Only accept candidates that land in a dictionary of the target script.
            if target_script and target_script != script and _known_word(candidate["text"]):
                if best is None or len(candidate["text"]) < len(best["text"]):
                    best = candidate
        if best:
            corrected_words.append(best["text"])
            changed += 1
        else:
            corrected_words.append(word)

    total = len(words) or 1
    confidence = changed / total if changed else 0.0
    corrected_text = text
    if changed:
        for (word, _), fixed in zip(words, corrected_words):
            corrected_text = corrected_text.replace(word, fixed, 1)

    return {
        "likely_wrong_layout": changed >= 2 and confidence >= 0.5,
        "corrected": corrected_text,
        "words_changed": changed,
        "total_words": len(words),
        "confidence": round(confidence, 2),
    }


if __name__ == "__main__":  # pragma: no cover
    for sample in ["ghbdtn rfr ndjb ltkf", "руддщ", "hello world"]:
        print(sample, "->", validate_layout(sample))

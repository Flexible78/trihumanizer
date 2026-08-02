/* TriHumanizer layout corrector — v1.6.1
 *
 * Detects text typed with the wrong physical keyboard layout and suggests or
 * applies the correct script. This is layout correction (same physical key
 * positions), not transliteration.
 *
 * Supported conversions:
 *   - English QWERTY <-> Russian JCUKEN
 *   - English QWERTY <-> Israeli Hebrew
 *   - Russian JCUKEN <-> Israeli Hebrew (via the shared physical key)
 *
 * The module is dependency-free and works in the browser and in Node (for
 * automated tests). Exposed as window.TriHumanizerLayout.
 */
(function (global) {
  "use strict";

  const VERSION = "1.6.1";

  /* QWERTY key -> character for each layout. */
  const RU = {
    q: "й", w: "ц", e: "у", r: "к", t: "е", y: "н", u: "г", i: "ш", o: "щ",
    p: "з", "[": "х", "]": "ъ",
    a: "ф", s: "ы", d: "в", f: "а", g: "п", h: "р", j: "о", k: "л", l: "д",
    ";": "ж", "'": "э",
    z: "я", x: "ч", c: "с", v: "м", b: "и", n: "т", m: "ь", ",": "б", ".": "ю",
  };

  const HE = {
    q: "/", w: "'", e: "ק", r: "ר", t: "א", y: "ט", u: "ו", i: "ן", o: "ם",
    p: "פ", "[": "]", "]": "[",
    a: "ש", s: "ד", d: "ג", f: "כ", g: "ע", h: "י", j: "ח", k: "ל", l: "ך",
    ";": "ף", "'": ",",
    z: "ז", x: "ס", c: "ב", v: "ה", b: "נ", n: "מ", m: "צ", ",": "ת", ".": "ץ",
  };

  function invert(map) {
    const out = {};
    Object.keys(map).forEach((key) => {
      out[map[key]] = key;
    });
    return out;
  }

  const RU_TO_KEY = invert(RU);
  const HE_TO_KEY = invert(HE);

  /* Convert a word between layouts via physical key positions.
   * fromCharToKey maps chars of the source script to QWERTY keys; when null the
   * source chars ARE the QWERTY keys. fromKeyToChar maps keys to the target
   * script; when null the target is the QWERTY key itself. */
  function convertWord(word, fromCharToKey, fromKeyToChar) {
    let result = "";
    for (const ch of word) {
      const lower = ch.toLowerCase();
      let converted = null;
      if (fromCharToKey) {
        const key = fromCharToKey[lower];
        if (key) converted = fromKeyToChar ? fromKeyToChar[key] : key;
      } else if (fromKeyToChar && fromKeyToChar[lower]) {
        converted = fromKeyToChar[lower];
      }
      result += converted || ch;
    }
    return result;
  }

  /* ---------- language scoring ---------- */

  const RU_WORDS = new Set(
    ("и в во не на я ты вы мы он она оно они это тот эта эти как так что чтобы если же только " +
      "привет здравствуйте пока спасибо пожалуйста извините да нет хорошо плохо очень много мало " +
      "можно нельзя нужно хочу могу будет есть был была были быть делать сделал сделала делаю " +
      "сказать сказал говорит сказала говорить понимаю понял поняла знаю знал знала вижу видел " +
      "слышу слышал писать написал написала пишешь читать прочитал читаю перевести переводить " +
      "перевод перевожу текст языка язык языки русский английский иврит переводчик работа работаю " +
      "работает работать работал дом дома город магазин письмо сообщение позвонить звонить телефон " +
      "времени время сейчас сегодня завтра вчера день ночь утро вечер человек люди друг подруга " +
      "семья мама папа брат сестра дети ребёнок вопрос ответ спросить отвечать ответить помочь " +
      "помощь просить прошу хотеть люблю нравится думать думаю подумать решить решил значит " +
      "конечно может быть наверное точно правда согласен согласна против вместе всегда никогда " +
      "иногда часто редко быстро медленно отлично ужасно нормально также ещё уже больше меньше " +
      "лучше хуже новый старая старый молодой большой маленький длинный короткий высокий низкий " +
      "дорогой дешёвый хороший интересный скучный сложный простой важный срочно потом раньше " +
      "позже около почти совсем деньги цена цены стоить стоит купить покупать продавать продать " +
      "заказ заказать доставка адрес улица номер квартира двери дверь открыть закрыть включить " +
      "выключить начать начал начала закончить закончил продолжать готово проверить проверка тест " +
      "тесты ошибка ошибки проблема проблемы решено исправить исправил версия версии обновить " +
      "установить скачать загрузить отправить отправлять получить получать прислать пришлите " +
      "отправьте прочитайте напишите позвоните приходите приходи приезжайте приезжай уходите " +
      "стой остановитесь подожди подождите извините простите большое огромное сердечное благодарю " +
      "благодарность добрый день доброе утро добрый вечер спокойной ночи до свидания до встречи " +
      "удачи успехов всего хорошего всего доброго пожелания уважением искренне ваш твоя мой моё " +
      "мои наши ваш ваша ваше ваши их его её нам вас тебе себе меня обращение просьба извинение " +
      "вопрос совет рекомендация задача цель результат итог вывод решение план действия шаги " +
      "этапы пункты список отчёт документ документы файл папка программа приложение система " +
      "сервер клиент компьютер ноутбук телефон планшет экран клавиатура мышь интернет браузер " +
      "страница сайт ссылка ссылки логин пароль аккаунт профиль настройки настройка параметры " +
      "опции режим режимы функция функции возможность возможности скорость качество количество " +
      "дата место расстояние направление маршрут билет билеты поезд самолёт аэропорт вокзал " +
      "станция остановка автобус метро такси машина автомобиль дорога перекрёсток пешеход " +
      "светофор правило правила закон законы права обязанности ответственность здоровье болезнь " +
      "врач больница аптека лекарство таблетка рецепт лечение доктор медсестра операция анализ " +
      "обследование приём запись очередь расписание график учёба школа университет институт " +
      "колледж курс курсы занятие урок домашнее задание экзамен оценка балл учитель преподаватель " +
      "студент студентка группа класс отпуск выходной праздник каникулы командировка поездка " +
      "путешествие отдых развлечение кино театр музей выставка концерт спектакль день рождения " +
      "новый год рождество пасха свадьба юбилей вечеринка встреча свидание знакомство дружба " +
      "отношения чувства эмоции настроение радость счастье грусть печаль страх тревога волнение " +
      "надежда вера уверенность сомнение решимость мужество смелость терпение настойчивость " +
      "цель амбиция мотивация вдохновение творчество искусство культура наука технология " +
      "инновация открытие исследование эксперимент гипотеза теория практика опыт навык умение " +
      "знание компетенция квалификация стаж резюме собеседование вакансия должность зарплата " +
      "оклад премия бонус страхование пенсия налог налоги финансы инвестиции капитал прибыль " +
      "убыток доход расход бюджет планирование стратегия менеджмент управление руководство " +
      "сотрудник коллега начальник директор менеджер специалист эксперт консультант партнёр " +
      "клиент поставщик подрядчик контракт договор соглашение сделка переговоры обсуждение " +
      "совещание переписка звонок звонки чат форум блог статья заметка новость новости пресса " +
      "журнал газета публикация реклама маркетинг бренд продукт услуга сервис качество гарантия " +
      "возврат обмен ремонт установка настройка конфигурация интеграция совместимость лицензия " +
      "ключ активация регистрация запись пароль безопасность защита шифрование конфиденциальность " +
      "политика правила условия приложение платформа инструмент средство способ метод подход " +
      "модель структура процесс процедура регламент стандарт норматив требование условие критерий " +
      "показатель индикатор метрика статистика данные информация сведения факты источники ссылки " +
      "доказательства подтверждение опровержение аргумент дискуссия спор обсуждение мнение точка " +
      "зрения позиция подход взгляд убеждение принцип ценность приоритет миссия видение стратегия " +
      "тактика график срок дедлайн этап фаза стадия шаг пункт раздел глава параграф приложение " +
      "комментарий примечание сноска цитата выдержка отрывок фрагмент кусок часть целое полный " +
      "частичный краткий подробный детальный общий частный конкретный абстрактный").split(/\s+/)
  );

  const EN_WORDS = new Set(
    ("the be to of and a in that have i it for not on with he as you do at this but his by from they " +
      "we say her she or an will my one all would there their what so up out if about who get which go me " +
      "when make can like time no just him know take people into year your good some could them see other " +
      "than then now look only come its over think also back after use two how our work first well way even " +
      "new want because any these give day most us is are was were been being has had did does please thanks " +
      "thank hello hi goodbye welcome sorry excuse pardon yes no okay fine great good bad nice wonderful " +
      "amazing beautiful happy sad angry tired hungry thirsty busy free ready done finished started stopped " +
      "working waiting talking speaking writing reading listening watching looking feeling thinking knowing " +
      "understanding helping asking answering telling saying giving taking making doing going coming seeing " +
      "hearing living loving hating wanting needing using trying finding losing winning buying selling paying " +
      "spending earning saving starting ending opening closing turning moving staying leaving arriving flying " +
      "driving walking running jumping swimming singing dancing playing studying learning teaching training " +
      "testing checking fixing repairing building creating designing developing programming coding debugging " +
      "installing updating upgrading downloading uploading sending receiving sharing publishing posting " +
      "commenting liking following subscribing connecting linking browsing searching opening saving deleting " +
      "editing copying pasting cutting selecting choosing deciding planning organizing preparing scheduling " +
      "meeting calling emailing messaging texting chatting translating interpreting explaining describing " +
      "presenting reporting reviewing analyzing evaluating comparing contrasting summarizing concluding " +
      "recommending suggesting asking clarifying confirming verifying approving rejecting accepting declining " +
      "agreeing disagreeing discussing debating arguing negotiating cooperating collaborating coordinating " +
      "communicating informing notifying warning advising encouraging motivating inspiring supporting " +
      "assisting guiding leading managing directing supervising monitoring controlling operating maintaining " +
      "replacing improving enhancing optimizing adjusting configuring customizing personalizing integrating " +
      "synchronizing backing restoring securing protecting encrypting hiding revealing exposing broadcasting " +
      "streaming ordering purchasing returning exchanging refunding canceling booking reserving rescheduling " +
      "postponing advancing delaying hurrying rushing waiting remaining departing landing taking off driving " +
      "traveling touring visiting exploring discovering finding seeking searching looking hunting chasing " +
      "catching holding keeping storing saving preserving retaining containing including excluding adding " +
      "removing erasing clearing emptying filling loading unloading packing unpacking building making " +
      "producing manufacturing constructing assembling fitting cleaning washing drying ironing folding " +
      "cooking baking boiling frying roasting grilling preparing serving eating drinking tasting enjoying " +
      "appreciating valuing respecting admiring praising apologizing forgiving tolerating permitting " +
      "allowing forbidding prohibiting preventing stopping blocking banning restricting limiting reducing " +
      "increasing growing expanding extending shrinking decreasing declining falling rising improving " +
      "worsening changing altering modifying transforming converting adapting substituting swapping " +
      "exchanging trading selling requesting demanding requiring needing wanting wishing hoping desiring " +
      "longing craving dreaming imagining visualizing arranging handling dealing coping solving resolving " +
      "settling finishing completing accomplishing achieving succeeding failing attempting practicing " +
      "researching investigating examining inspecting analyzing assessing evaluating judging rating " +
      "scoring grading ranking comparing matching pairing grouping sorting classifying categorizing " +
      "labeling tagging naming identifying recognizing remembering recalling forgetting memorizing noting " +
      "recording documenting logging tracking monitoring observing highlighting emphasizing underlining " +
      "quoting citing referencing sourcing attributing crediting acknowledging congratulating celebrating " +
      "commemorating honoring rewarding compensating reimbursing repaying settling clearing reconciling " +
      "auditing validating certifying endorsing funding investing financing sponsoring donating " +
      "contributing volunteering aiding nursing caring tending nurturing raising feeding clothing " +
      "sheltering housing accommodating welcoming hosting entertaining amusing delighting pleasing " +
      "satisfying fulfilling meeting exceeding surpassing outperforming beating defeating conquering " +
      "overcoming excelling thriving prospering flourishing blooming developing maturing aging " +
      "progressing evolving adapting growing becoming turning concentrating focusing centering targeting " +
      "aiming directing spotlighting stressing underscoring accentuating exaggerating minimizing " +
      "downplaying softening tempering moderating easing relaxing loosening tightening strengthening " +
      "weakening adding subtracting multiplying dividing counting calculating computing measuring " +
      "weighing quantifying estimating approximating guessing assuming supposing presuming hypothesizing " +
      "theorizing speculating wondering pondering contemplating meditating reflecting deliberating " +
      "considering balancing determining resolving store support glasses hours stock email phone address " +
      "model order exchange return available optical customer service opening closed open monday tuesday " +
      "wednesday thursday friday saturday sunday week month year today tomorrow yesterday morning evening " +
      "afternoon night price cost discount delivery shipping contact question answer request please " +
      "exchange glasses order number model in stock opening hours").split(/\s+/)
  );

  const HE_WORDS = new Set(
    ("שלום מה שלומך תודה בבקשה סליחה מצטער כן לא טוב רע יפה נהדר נפלא מדהים שמח עצוב כועס עייף " +
      "רעב צמא עסוק פנוי מוכן גמור סיים התחיל עבד עובד מחכה מדבר כותב קורא מקשיב מסתכל מרגיש " +
      "חושב יודע מבין עוזר שואל עונה אומר מספר נותן לוקח עושה בא הולך רואה שומע נוגע טועם מריח " +
      "אוהב שונא רוצה צריך מנסה מוצא מפסיד מנצח קונה מוכר משלם עולה מרוויח מוציא חוסך מתחיל " +
      "מסיים פותח סוגר זז נשאר עוזב מגיע טס נוהג רץ קופץ שוחה שר רוקד משחק עובד לומד מלמד " +
      "מתאמן בודק מתקן בונה יוצר מפתח מתכנת מתקין מעדכן מוריד מעלה שולח מקבל משתף מפרסם מגיב " +
      "אוהב עוקב מתחבר מקשר מחפש מוצא שומר מוחק עורך מעתיק מדביק חותך בוחר מחליט מתכנן מארגן " +
      "מכין קובע נפגש מתקשר שולח הודעה מצ'וטט מדבר כותב מתרגם מפרש מסביר מציג מדווח סוקר מנתח " +
      "משווה מעריך מסכם ממליץ מציע שואל מברר מאשר מאמת בודק מסכים דוחה מקבל מסרב מתווכח דן " +
      "מתלבט משתף פעולה מתאם מעדכן מודיע מזהיר מייעץ מעודד מניע תומך עוזר מנחה מוביל מנהל " +
      "מכוון מפקח שולט מפעיל מריץ מתחזק משרת מתקן מחליף משדרג משפר מייעל מתאים מגדיר מתחבר " +
      "משלב מסנכרן מגבה משחזר מאבטח מגן מצפין מסתיר חושף מפרסם משדר מזרים מוריד מסנכרן שומר " +
      "מזמין קונה מחזיר מחליף מבטל דוחה מזרז מעכב ממהר נשאר עוזב יוצא מגיע נוחת ממריא נוסע " +
      "מטייל מבקר מגלה תופס מאחסן מכיל כולל מוציא מוסיף מסיר מוחק מנקה ממלא מרוקן טוען פורק " +
      "אורז מייצר מרכיב מתאים מטגן צולה מגיש אוכל שותה טועם נהנה מעריך מכבד מעריץ משבח מודה " +
      "מתנצל סולח מבין מקבל סובל מרשה אוסר מונע עוצר חוסם מגביל מצמצם מגדיל מקטין נופל משתפר " +
      "מחמיר משנה הופך מתפתח גדל מתקדם מבקש דורש מקווה חולם מדמיין מארגן קובע מתאם מטפל פותר " +
      "מסיים משלים משיג מצליח נכשל מנסה מתרגל חוקר בודק מעריך שופט מדרג משווה תואם מקשר מקבץ " +
      "ממיין מסווג מתייג שם מזהה מכיר זוכר שוכח מציין מתעד רושם עוקב צופה בוחן מסכם מדגיש " +
      "מצטט מייחס נותן קרדיט מתחרט מברך מנציח מכיר מתגמל מפצה מחזיר משלם מסדר מאשר תומך מממן " +
      "תורם מתנדב מסייע מקיים משמר מגן מאבטח מחזק משדרג מחדש משקם בונה מחדש מרפא מטפל מטפח " +
      "מאכיל מלביש מחסה מארח מבדר משמח משביע עונה עוקף מתגבר בולט משגשג פורח גדל מזדקן משתנה " +
      "ממזער מרכך מחליש מוסיף מחסיר מכפיל מחלק סופר מחשב מודד שוקל מנחש מניח משער מהרהר " +
      "שוקל קובע מסיים פותר").split(/\s+/)
  );

  const LANG_DICTS = { ru: RU_WORDS, en: EN_WORDS, he: HE_WORDS };

  function normalize(word) {
    return word
      .toLowerCase()
      .replace(/ё/g, "е")
      .replace(/[’']/g, "'");
  }

  function buildBigrams(words, top = 400) {
    const counts = {};
    words.forEach((word) => {
      for (let i = 0; i < word.length - 1; i += 1) {
        const bigram = word.slice(i, i + 2);
        counts[bigram] = (counts[bigram] || 0) + 1;
      }
    });
    return new Set(
      Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, top)
        .map((entry) => entry[0])
    );
  }

  const RU_BIGRAMS = buildBigrams([...RU_WORDS]);
  const EN_BIGRAMS = buildBigrams([...EN_WORDS]);
  const HE_BIGRAMS = buildBigrams([...HE_WORDS]);
  const LANG_BIGRAMS = { ru: RU_BIGRAMS, en: EN_BIGRAMS, he: HE_BIGRAMS };

  function isCyrillic(ch) {
    return /[а-яёА-ЯЁ]/.test(ch);
  }

  function isHebrewChar(ch) {
    const code = ch.codePointAt(0);
    return code >= 0x0590 && code <= 0x05ff;
  }

  function scriptOf(word) {
    let cyrillic = 0;
    let hebrew = 0;
    let latin = 0;
    for (const ch of word) {
      if (isCyrillic(ch)) cyrillic += 1;
      else if (isHebrewChar(ch)) hebrew += 1;
      else if (/[a-zA-Z]/.test(ch)) latin += 1;
    }
    const total = cyrillic + hebrew + latin;
    if (!total) return null;
    if (cyrillic / total > 0.85) return "ru";
    if (hebrew / total > 0.85) return "he";
    if (latin / total > 0.85) return "en";
    return null; // mixed within the word — never convert
  }

  /* Score how word-like a word is in a language, 0..1. */
  function languageScore(word, lang) {
    const normalized = normalize(word);
    if (!normalized) return 0;
    const dict = LANG_DICTS[lang];
    let dictScore = 0;
    if (dict.has(normalized)) {
      dictScore = 1;
    } else {
      for (let len = Math.min(normalized.length - 1, 6); len >= 4; len -= 1) {
        const prefix = normalized.slice(0, len);
        const suffix = normalized.slice(-len);
        if (dict.has(prefix) || dict.has(suffix)) {
          dictScore = 0.62;
          break;
        }
      }
    }

    const bigrams = LANG_BIGRAMS[lang];
    let hit = 0;
    let total = 0;
    for (let i = 0; i < normalized.length - 1; i += 1) {
      total += 1;
      if (bigrams.has(normalized.slice(i, i + 2))) hit += 1;
    }
    const bigramScore = total ? hit / total : 0;

    return 0.62 * dictScore + 0.38 * bigramScore;
  }

  /* ---------- protection ---------- */

  const PROTECTED_PATTERNS = [
    /https?:\/\/[^\s<>"']+/gi,
    /www\.[^\s<>"']+/gi,
    /[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/gi,
    /(?:^|\s)[a-z]:[\\/][^\s<>"']+/gi,
    /(?:^|\s)[\\/][^\s<>"']*/gi,
    /(?:^|\s)(?:v)?\d+\.\d+(?:\.\d+)?[^\s]*/gi,
    /#[a-z0-9_]+/gi,
    /@[a-z0-9_]+/gi,
    /(?:ctrl|cmd|alt|shift|fn)\s*\+\s*[a-z0-9]+/gi,
    /api[_\-.][a-z0-9_\-.]+/gi,
    /[\w.-]+\s*=\s*[^\s<>"']+/gi,
  ];

  /* Return [start, end) spans of protected regions in the text. */
  function protectedSpans(text) {
    const spans = [];
    PROTECTED_PATTERNS.forEach((pattern) => {
      const re = new RegExp(pattern.source, pattern.flags);
      let match;
      while ((match = re.exec(text)) !== null) {
        spans.push([match.index, match.index + match[0].length]);
        if (match.index === re.lastIndex) re.lastIndex += 1;
      }
    });
    // Pure numbers anywhere (outside URL/version spans already covered).
    const number = /\b\d+(?:[.,]\d+)*\b/g;
    let match;
    while ((match = number.exec(text)) !== null) {
      spans.push([match.index, match.index + match[0].length]);
    }
    return spans;
  }

  function insideSpans(start, end, spans) {
    return spans.some(([s, e]) => start < e && end > s);
  }

  /* ---------- tokenizer ---------- */

  function tokenize(text) {
    const tokens = [];
    const regex = /([\u0590-\u05ff\u0400-\u04ffa-zA-Z]+(?:['’-][\u0590-\u05ff\u0400-\u04ffa-zA-Z]+)*)|(\s+)|(\d+(?:[.,]\d+)*)|([^\s\w\u0590-\u05ff\u0400-\u04ff]+)/gu;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match[1]) {
        tokens.push({ type: "word", value: match[1], start: match.index });
      } else if (match[2]) {
        tokens.push({ type: "space", value: match[2], start: match.index });
      } else if (match[3]) {
        tokens.push({ type: "number", value: match[3], start: match.index });
      } else {
        tokens.push({ type: "punct", value: match[4], start: match.index });
      }
    }
    return tokens;
  }

  /* ---------- case preservation ---------- */

  function applyCase(original, converted) {
    if (/^[A-ZА-ЯЁ]+$/.test(original)) return converted.toUpperCase();
    if (/^[A-ZА-ЯЁ]/.test(original) && converted.length > 1) {
      return converted.charAt(0).toUpperCase() + converted.slice(1);
    }
    return converted;
  }

  /* ---------- candidates ---------- */

  function candidates(word) {
    const script = scriptOf(word);
    const list = [];
    if (script === "en") {
      list.push({ lang: "ru", text: convertWord(word, null, RU) });
      list.push({ lang: "he", text: convertWord(word, null, HE) });
    } else if (script === "ru") {
      list.push({ lang: "en", text: convertWord(word, RU_TO_KEY, null) });
      list.push({ lang: "he", text: convertWord(word, RU_TO_KEY, HE) });
    } else if (script === "he") {
      list.push({ lang: "en", text: convertWord(word, HE_TO_KEY, null) });
      list.push({ lang: "ru", text: convertWord(word, HE_TO_KEY, RU) });
    }
    return list;
  }

  /**
   * Correct a text fragment.
   *
   * @param {string} text - raw input
   * @param {object} options - { sourceLanguage: "auto"|"ru"|"en"|"he" }
   * @returns {{ text: string, confidence: number, level: "high"|"medium"|"none",
   *            changed: boolean, conversions: Array<{from:string,to:string,lang:string}> }}
   */
  function correctText(text, options = {}) {
    const sourceLanguage = options.sourceLanguage || "auto";
    if (!text || !text.trim()) {
      return { text, confidence: 0, level: "none", changed: false, conversions: [] };
    }

    const spans = protectedSpans(text);
    const tokens = tokenize(text);
    const conversions = [];
    let convertedWords = 0;
    let totalWords = 0;
    let confidenceSum = 0;

    const output = tokens.map((token) => {
      if (token.type === "word") totalWords += 1;
      if (token.type !== "word") return token.value;
      const end = token.start + token.value.length;
      if (insideSpans(token.start, end, spans)) return token.value;

      // Words touching a digit (version numbers, identifiers, code) stay put.
      const before = text.slice(Math.max(0, token.start - 2), token.start);
      const after = text.slice(end, end + 2);
      if (/\d/.test(before) || /\d/.test(after) || /\d/.test(token.value)) return token.value;

      const originalScript = scriptOf(token.value);
      if (!originalScript) return token.value;

      const originalScore = languageScore(token.value, originalScript);
      let best = null;

      candidates(token.value).forEach((candidate) => {
        if (!candidate.text || candidate.text === token.value) return;
        const candidateScore = languageScore(candidate.text, candidate.lang);
        let boost = 0;
        if (sourceLanguage === candidate.lang && sourceLanguage !== originalScript) boost = 0.12;
        if (sourceLanguage === originalScript) boost = 0.12;
        const effective = candidateScore + boost;
        if (!best || effective > best.score) best = { ...candidate, score: effective };
      });

      if (!best) return token.value;

      const gain = best.score - originalScore;
      if (gain >= 0.22 && best.score >= 0.42) {
        const corrected = applyCase(token.value, best.text);
        conversions.push({ from: token.value, to: corrected, lang: best.lang });
        convertedWords += 1;
        confidenceSum += Math.min(1, best.score);
        return corrected;
      }
      return token.value;
    });

    let confidence = 0;
    if (convertedWords > 0 && totalWords > 0) {
      const coverage = convertedWords / totalWords;
      const averageScore = confidenceSum / convertedWords;
      confidence = 0.5 * coverage + 0.5 * averageScore;
    }

    let level = "none";
    if (confidence >= 0.72) level = "high";
    else if (confidence >= 0.45) level = "medium";

    return {
      text: output.join(""),
      confidence: Math.round(confidence * 100) / 100,
      level,
      changed: convertedWords > 0,
      conversions,
    };
  }

  const api = { correctText, convertWord, languageScore, scriptOf, VERSION };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  global.TriHumanizerLayout = api;
})(typeof window !== "undefined" ? window : globalThis);

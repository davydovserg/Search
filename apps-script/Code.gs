/**
 * Приёмник для программы Search. Отдельный проект на script.google.com —
 * существующий скрипт внутри таблицы не трогает.
 *
 * Настройка (один раз):
 * 1. script.google.com → «Новый проект» → вставить этот код.
 * 2. Настройки проекта (шестерёнка) → «Свойства скрипта» → добавить TOKEN = любой длинный пароль
 *    (тот же вписать в config.json → "token").
 * 3. «Начать развёртывание» → «Новое развёртывание» → тип «Веб-приложение»,
 *    «Запуск от имени: я», «Доступ: все» → скопировать URL в config.json → "webapp_url".
 */
function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var token = PropertiesService.getScriptProperties().getProperty('TOKEN');
    if (!token || body.token !== token) return json_({ ok: false, error: 'bad token' });

    var ss = SpreadsheetApp.openById(body.spreadsheetId);
    var sh = null;
    if (body.gid !== null && body.gid !== undefined && body.gid !== '') {
      sh = ss.getSheets().filter(function (s) { return String(s.getSheetId()) === String(body.gid); })[0] || null;
    }
    if (!sh && body.sheet) sh = ss.getSheetByName(body.sheet) || ss.insertSheet(body.sheet);
    if (!sh) return json_({ ok: false, error: 'sheet not found' });

    var header = body.header;
    var idCol = header.length; // ID — последняя колонка
    if (sh.getLastRow() === 0) {
      sh.getRange(1, 1, 1, header.length).setValues([header]).setFontWeight('bold');
      sh.setFrozenRows(1);
    }

    var existing = {};
    var last = sh.getLastRow();
    if (last > 1) {
      sh.getRange(2, idCol, last - 1, 1).getValues().forEach(function (r) { existing[String(r[0])] = true; });
    }
    var fresh = body.rows.filter(function (r) { return !existing[String(r[idCol - 1])]; });
    if (fresh.length) {
      var start = sh.getLastRow() + 1;
      var rng = sh.getRange(start, 1, fresh.length, header.length);
      rng.setNumberFormat('@'); // телефоны и ID как текст
      rng.setValues(fresh);
    }
    return json_({ ok: true, added: fresh.length, skipped: body.rows.length - fresh.length });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

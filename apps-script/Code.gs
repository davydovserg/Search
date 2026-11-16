/**
 * Приёмник для программы Search. Отдельный проект на script.google.com —
 * существующий скрипт внутри таблицы не трогает.
 *
 * Пишет строки в формате вкладки contacts:
 * key | name | category | address | phones | phone_1 | phone_2 | phone_3 | note | url
 * Существующие строки не меняет, дубли (по key, ID Яндекса или телефону) пропускает.
 *
 * Настройка: вставить код → «Начать развёртывание» → «Новое развёртывание» → «Веб-приложение»,
 * «Запуск от имени: я», «Доступ: все» → URL в config.json → "webapp_url".
 */

// Пароль — тот же, что в config.json → "token". Можно задать и в «Свойствах скрипта» (TOKEN).
var TOKEN_INLINE = '';

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var token = PropertiesService.getScriptProperties().getProperty('TOKEN') || TOKEN_INLINE;
    if (!token || body.token !== token) return json_({ ok: false, error: 'bad token' });
    return json_(appendRows_(body.spreadsheetId, body.gid, body.sheet, body.rows));
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

var HEADER = ['key', 'name', 'category', 'address', 'phones', 'phone_1', 'phone_2', 'phone_3', 'note', 'url'];

function appendRows_(spreadsheetId, gid, sheetName, rows) {
  var ss = SpreadsheetApp.openById(spreadsheetId);
  var sh = null;
  if (gid !== null && gid !== undefined && gid !== '') {
    sh = ss.getSheets().filter(function (s) { return String(s.getSheetId()) === String(gid); })[0] || null;
  }
  if (!sh && sheetName) sh = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);
  if (!sh) return { ok: false, error: 'sheet not found' };

  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, HEADER.length).setValues([HEADER]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }

  var seen = {};
  var last = sh.getLastRow();
  if (last > 1) {
    sh.getRange(2, 1, last - 1, Math.max(sh.getLastColumn(), HEADER.length)).getDisplayValues().forEach(function (r) {
      seen['k:' + r[0]] = true;
      var text = r.join(' ');
      (text.match(/\/maps\/org\/[^\/\s]+\/(\d+)/g) || []).forEach(function (m) { seen['id:' + m.split('/').pop()] = true; });
      (text.match(/\+7\d{10}/g) || []).forEach(function (p) { seen['p:' + p] = true; });
    });
  }

  var fresh = [];
  rows.forEach(function (r) {
    var id = (String(r[0]).match(/(\d+)$/) || [])[1];
    var phones = String(r[4]).match(/\+7\d{10}/g) || [];
    var dup = seen['k:' + r[0]] || (id && seen['id:' + id]) || phones.some(function (p) { return seen['p:' + p]; });
    if (dup) return;
    seen['k:' + r[0]] = true;
    if (id) seen['id:' + id] = true;
    phones.forEach(function (p) { seen['p:' + p] = true; });
    fresh.push(r.slice(0, HEADER.length));
  });

  if (fresh.length) {
    var rng = sh.getRange(sh.getLastRow() + 1, 1, fresh.length, HEADER.length);
    rng.setNumberFormat('@'); // телефоны как текст, с «+»
    rng.setValues(fresh);
  }
  return { ok: true, added: fresh.length, skipped: rows.length - fresh.length };
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

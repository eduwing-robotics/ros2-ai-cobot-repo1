const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function viewer() {
  const ids = {};
  for (const id of ['viewport','report-image','zoom','zoom-value','fit','actual','search','finding-count','no-match','filter-status']) {
    ids[id] = { style: {}, value: '', textContent: '', hidden: false, events: {},
      addEventListener(name, fn) { this.events[name] = fn; },
      scrollTo(value) { this.lastScroll = value; } };
  }
  ids.zoom.value = '100';
  ids['report-image'].naturalWidth = 2048;
  const rows = [ { textContent: 'GPU-01 방향 오류 UNKNOWN', hidden: false },
                 { textContent: 'HBM-03 부품 누락 UNKNOWN', hidden: false } ];
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'demo_assets/viewer.js'),'utf8'), {
    document: { getElementById: id => ids[id], querySelectorAll: () => rows }
  });
  return { ids, rows };
}

test('fit, zoom and native size only change CSS dimensions', () => {
  const { ids } = viewer();
  assert.equal(ids['report-image'].style.width, '100%');
  ids.zoom.value = '200'; ids.zoom.events.input();
  assert.equal(ids['report-image'].style.width, '200%');
  ids.actual.events.click();
  assert.equal(ids['report-image'].style.width, '2048px');
  ids.fit.events.click();
  assert.equal(ids['report-image'].style.width, '100%');
  assert.equal(ids.viewport.lastScroll.left, 0);
});

test('search filters rows, retains original text and clears correctly', () => {
  const { ids, rows } = viewer();
  const originals = rows.map(r => r.textContent);
  ids.search.value = 'gpu'; ids.search.events.input();
  assert.deepEqual(rows.map(r => r.hidden), [false, true]);
  assert.equal(ids['finding-count'].textContent, '1 / 2');
  ids.search.value = 'NOT_FOUND'; ids.search.events.input();
  assert.equal(ids['no-match'].hidden, false);
  ids.search.value = ''; ids.search.events.input();
  assert.deepEqual(rows.map(r => r.hidden), [false, false]);
  assert.equal(ids['no-match'].hidden, true);
  assert.deepEqual(rows.map(r => r.textContent), originals);
});

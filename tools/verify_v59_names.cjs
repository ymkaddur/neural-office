// Optional Windows developer check. Requires Playwright and an installed Edge.
const assert = require('node:assert/strict');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright');

async function main() {
  const checkout = path.resolve(__dirname, '..');
  const cases = JSON.parse(execFileSync('py', ['-3.12', '-B', '-c',
    "import json,runpy;print(json.dumps(runpy.run_path('tests/test_v59_names.py')['CASES']))"],
    {cwd:checkout, encoding:'utf8'}));
  assert.ok(cases.length);
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const page = await browser.newPage({javaScriptEnabled:false});
    const session = await page.context().newCDPSession(page);
    for (const [id, html, expected] of cases) {
      await page.setContent(html);
      const {nodes} = await session.send('Accessibility.getFullAXTree');
      const fields = nodes.filter(n => !n.ignored && n.role?.value === 'textbox');
      assert.equal(fields.length, 1, id);
      assert.equal(fields[0].name.value, expected, id);
    }
    console.log(`${cases.length} accessible names matched Edge ${browser.version()}.`);
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });

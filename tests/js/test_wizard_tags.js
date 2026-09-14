/**
 * Regression tests for wizard tag persistence (accent markers + catchphrases).
 *
 * Both defects below silently destroyed user input with no error anywhere:
 *   A. The tag inputs committed only on Enter, so text typed and then clicked
 *      away from never reached state, localStorage, or the create payload.
 *   B. restoreFormValues() ran only from resumeDraft(), so a reload showed
 *      empty fields even though the values were still in localStorage.
 *
 * Run: node tests/js/test_wizard_tags.js
 * Override the file under test with WIZ=/path/to/wizard.js (used to confirm
 * these tests actually fail against the pre-fix version).
 */
const path = require('path');
const { createHarness } = require('./wizard_dom_harness.js');

const WIZARD = process.env.WIZ ||
    path.join(__dirname, '..', '..', 'character_creator', 'static', 'wizard.js');

let pass = 0, fail = 0;
function check(name, cond, extra = '') {
    if (cond) { console.log(`  PASS  ${name}`); pass++; }
    else { console.log(`  FAIL  ${name} ${extra}`); fail++; }
}

const { getEl, localStorage, lookup } = createHarness(WIZARD);
const WizardUI = lookup('WizardUI');

function fresh(seed) {
    localStorage._seed(seed ? { wizard_state: JSON.stringify(seed) } : {});
    // Clear any input text left over from a previous case.
    getEl('accent-input').value = '';
    getEl('catchphrase-input').value = '';
    const w = new WizardUI();
    w.onStepEnter = () => {};   // stub: real one hits the network
    w.renderTags = () => {};    // stub: DOM paint only
    w.bindEvents();
    return w;
}

console.log('\n-- Defect A: tag text typed but never Enter-committed --');

let w = fresh();
getEl('accent-input').value = 'Talks in rapid-fire bursts';
getEl('accent-input').fire('blur');
check('blur commits accent marker',
    (w.state.get('accent_markers') || []).includes('Talks in rapid-fire bursts'),
    JSON.stringify(w.state.get('accent_markers')));

w = fresh();
getEl('catchphrase-input').value = 'Pending catchphrase';
w.goToStep(2);
check('goToStep flushes pending catchphrase',
    (w.state.get('catchphrases') || []).includes('Pending catchphrase'),
    JSON.stringify(w.state.get('catchphrases')));

const persisted = JSON.parse(localStorage.getItem('wizard_state')).data.catchphrases || [];
check('flushed value persisted to localStorage',
    persisted.includes('Pending catchphrase'), JSON.stringify(persisted));

w = fresh();
getEl('accent-input').value = 'Dup test';
getEl('accent-input').fire('blur');
getEl('accent-input').value = 'Dup test';
w.goToStep(1);
const dups = (w.state.get('accent_markers') || []).filter(x => x === 'Dup test').length;
check('no duplicate on blur + nav', dups === 1, `count=${dups}`);

w = fresh();
getEl('accent-input').value = '   ';
w.goToStep(1);
check('whitespace-only input adds nothing',
    (w.state.get('accent_markers') || []).length === 0);

console.log('\n-- Defect B: saved values invisible until Resume clicked --');

w = fresh({
    currentStep: 2, savedAt: new Date().toISOString(),
    data: {
        char_name: 'testchar', catchphrases: ['Saved one'],
        accent_markers: ['Saved marker'], system_prompt: 'SP',
    },
});
const painted = [];
w.renderTags = (type, vals) => painted.push([type, vals]);
w.checkForDraft();
check('checkForDraft repaints tag lists', painted.length === 2, JSON.stringify(painted));
check('  accent tags repainted from state',
    JSON.stringify((painted.find(p => p[0] === 'accent') || [])[1]) === '["Saved marker"]');
check('  catchphrase tags repainted from state',
    JSON.stringify((painted.find(p => p[0] === 'catchphrase') || [])[1]) === '["Saved one"]');
check('  text field repainted too', getEl('system-prompt').value === 'SP');
check('draftStep NOT adopted (wizard still shows step 0)', w.state.currentStep === 0,
    `currentStep=${w.state.currentStep}`);

console.log(`\n${pass} passed, ${fail} failed\n`);
process.exit(fail ? 1 : 0);

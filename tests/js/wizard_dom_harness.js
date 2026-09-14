/**
 * Minimal DOM + localStorage shim for exercising character_creator/static/wizard.js
 * in plain Node, with no jsdom and no package.json.
 *
 * wizard.js is a browser script that ends by constructing a WizardUI and binding
 * DOMContentLoaded. We run it inside a vm context with just enough of the DOM
 * surface it touches, so its logic can be tested headlessly.
 *
 * Class declarations are lexical, so they never land on the context object --
 * reach them with lookup('WizardUI') rather than sandbox.WizardUI.
 */
const fs = require('fs');
const vm = require('vm');

function mkEl(id) {
    return {
        id, value: '', textContent: '', innerHTML: '', checked: false,
        dataset: {}, style: {}, _handlers: {},
        classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
        focus() {}, remove() {}, appendChild() {}, insertBefore() {},
        addEventListener(ev, fn) { (this._handlers[ev] ||= []).push(fn); },
        // Test hook: synthesize an event on this element.
        fire(ev, arg) {
            (this._handlers[ev] || []).forEach(fn =>
                fn(arg || { preventDefault() {}, key: '' }));
        },
        querySelector() { return mkEl('q'); },
        querySelectorAll() { return []; },
    };
}

function createHarness(wizardPath) {
    const els = new Map();
    const getEl = id => {
        if (!els.has(id)) els.set(id, mkEl(id));
        return els.get(id);
    };

    let store = {};
    const localStorage = {
        getItem: k => (k in store ? store[k] : null),
        setItem: (k, v) => { store[k] = String(v); },
        removeItem: k => { delete store[k]; },
        _seed: s => { store = s; },
    };

    const document = {
        getElementById: getEl,
        querySelector: () => mkEl('q'),
        querySelectorAll: () => [],
        createElement: () => mkEl('new'),
        addEventListener: () => {},
    };

    const sandbox = {
        document, localStorage, console,
        window: { location: { href: '' } },
        navigator: { mediaDevices: {} },
        fetch: async () => ({ ok: true, json: async () => ({}) }),
        setTimeout, clearTimeout, setInterval, clearInterval, Date, JSON, Math,
        showToast: () => {}, api: async () => ({}),
    };
    sandbox.globalThis = sandbox;
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(wizardPath, 'utf8'), sandbox, { filename: 'wizard.js' });

    return { sandbox, getEl, els, localStorage, lookup: n => vm.runInContext(n, sandbox) };
}

module.exports = { createHarness };

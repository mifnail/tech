const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const React = require("react");
const root = path.resolve(__dirname, "..");

function sourceLoader(mocks = {}, globals = {}) {
  const cache = new Map();
  const context = vm.createContext({
    console, setTimeout, clearTimeout, FormData, File, ...globals,
  });
  function load(filename) {
    filename = path.resolve(root, filename);
    if (!path.extname(filename)) {
      filename = [".ts", ".tsx", ".js"].map((ext) => filename + ext).find(fs.existsSync);
    }
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} };
    cache.set(filename, module);
    const source = fs.readFileSync(filename, "utf8").replaceAll("import.meta.env.DEV", "false");
    const result = ts.transpileModule(source, { fileName: filename, compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true, allowJs: true,
    } });
    const localRequire = (name) => {
      if (Object.hasOwn(mocks, name)) return mocks[name];
      return name.startsWith(".") ? load(path.resolve(path.dirname(filename), name)) : require(name);
    };
    vm.runInContext(`(function(require, module, exports) {${result.outputText}\n})`, context, { filename })(localRequire, module, module.exports);
    return module.exports;
  }
  return load;
}

const settle = () => new Promise((resolve) => setImmediate(resolve));
const response = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data });
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function restoreHarness({ fetch, flush = async () => {} }) {
  const states = new Map();
  let active, index, effects = [], tree;
  const messages = [], events = [], session = new Map();
  const fakeReact = {
    ...React,
    useState(initial) {
      const slots = states.get(active), slot = index++;
      if (!(slot in slots)) slots[slot] = typeof initial === "function" ? initial() : initial;
      return [slots[slot], (next) => { slots[slot] = typeof next === "function" ? next(slots[slot]) : next; }];
    },
    useRef(initial) {
      const slots = states.get(active), slot = index++;
      if (!(slot in slots)) slots[slot] = { current: initial };
      return slots[slot];
    },
    useEffect(effect, deps) {
      const slots = states.get(active), slot = index++;
      if (!slots[slot] || deps.some((value, i) => value !== slots[slot][i])) {
        slots[slot] = deps;
        effects.push(effect);
      }
    },
    useContext: () => (message) => messages.push(message),
  };
  const load = sourceLoader({
    react: fakeReact,
    "react-dom": { createPortal: (children) => children },
    "../lib/store": { store: { flushAttendance: async () => { events.push("flush"); await flush(); } } },
  }, {
    fetch: async (url, options) => { events.push([url, options]); return fetch(url, options); },
    window: { location: { reload: () => events.push("reload") } },
    sessionStorage: { setItem: (key, value) => session.set(key, value) },
    document: { body: { style: {} } },
  });
  const Component = load("src/components/RestoreDatabase.tsx").default;
  function expand(node, key) {
    if (node == null || typeof node === "boolean") return null;
    if (Array.isArray(node)) return node.map((child, i) => expand(child, key + "." + i));
    if (typeof node !== "object") return node;
    if (node.type === React.Fragment) return expand(node.props.children, key + ".fragment");
    if (typeof node.type === "function") {
      active = key;
      index = 0;
      if (!states.has(key)) states.set(key, []);
      return expand(node.type(node.props), key + ".child");
    }
    if (typeof node.type !== "string") return null;
    return { type: node.type, props: { ...node.props, children: expand(node.props.children, key + ".children") } };
  }
  function render() {
    tree = expand(React.createElement(Component), "restore");
    const pending = effects;
    effects = [];
    for (const effect of pending) effect();
    return tree;
  }
  function all(predicate) {
    const found = [];
    function walk(node) {
      if (Array.isArray(node)) { node.forEach(walk); return; }
      if (!node || typeof node !== "object") return;
      if (predicate(node)) found.push(node);
      walk(node.props.children);
    }
    walk(tree);
    return found;
  }
  function text(node) {
    if (Array.isArray(node)) return node.map(text).join("");
    if (!node || typeof node === "boolean") return "";
    return typeof node === "object" ? text(node.props.children) : String(node);
  }
  return {
    render, all, text, events, messages, session,
    async ready() { render(); await settle(); render(); },
    button(label) {
      const button = all((node) => node.type === "button" && text(node) === label)[0];
      if (!button) throw new Error(`Button not found: ${label}`);
      return button;
    },
    click(label) {
      const button = this.button(label);
      if (button.props.disabled) throw new Error(`Button disabled: ${label}`);
      const result = button.props.onClick();
      render();
      return result;
    },
    content() { return text(tree); },
  };
}

module.exports = { root, sourceLoader, settle, response, deferred, restoreHarness };

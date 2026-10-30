// Renders the design artboards outside the design canvas, so builders can open and screenshot
// them. It expands <x-dc> templates: {{path}} holes, <sc-for> and <sc-if>, from renderVals().
(function () {
  class DCLogic { constructor(props) { this.props = props || {}; this.state = {}; } setState() {} forceUpdate() {} }
  function lookup(scope, path) {
    return path.trim().split('.').reduce((v, k) => (v == null ? undefined : v[k]), scope);
  }
  function fill(text, scope) {
    return text.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (_, p) => {
      const v = lookup(scope, p);
      return v == null || typeof v === 'function' ? '' : String(v);
    });
  }
  function expand(node, scope) {
    if (node.nodeType === 3) return [document.createTextNode(fill(node.textContent, scope))];
    if (node.nodeType !== 1) return [];
    const tag = node.tagName.toLowerCase();
    if (tag === 'sc-for') {
      const list = lookup(scope, (node.getAttribute('list') || '').replace(/[{}]/g, '')) || [];
      const as = node.getAttribute('as') || 'item';
      const out = [];
      list.forEach((v, i) => {
        const inner = Object.assign({}, scope, { [as]: v, $index: i });
        node.childNodes.forEach((c) => out.push(...expand(c, inner)));
      });
      return out;
    }
    if (tag === 'sc-if') {
      const v = lookup(scope, (node.getAttribute('value') || '').replace(/[{}]/g, ''));
      if (!v) return [];
      const out = [];
      node.childNodes.forEach((c) => out.push(...expand(c, scope)));
      return out;
    }
    if (tag === 'helmet') {
      node.querySelectorAll('style').forEach((s) => document.head.appendChild(s.cloneNode(true)));
      return [];
    }
    const el = document.createElement(node.tagName);
    for (const a of node.attributes) {
      if (/^on[A-Z]/.test(a.name)) continue;
      el.setAttribute(a.name, fill(a.value, scope));
    }
    node.childNodes.forEach((c) => expand(c, scope).forEach((n) => el.appendChild(n)));
    return [el];
  }
  window.addEventListener('DOMContentLoaded', () => {
    const script = document.querySelector('script[type="text/x-dc"]');
    const root = document.querySelector('x-dc');
    if (!script || !root) return;
    const Component = new Function('DCLogic', script.textContent + '\nreturn Component;')(DCLogic);
    const scope = new Component({}).renderVals() || {};
    const out = [];
    root.childNodes.forEach((c) => out.push(...expand(c, scope)));
    root.replaceWith(...out);
  });
})();

// Tiny DOM helpers — the whole "framework".

export const byId = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;

/** `document.createElement` wrapper: `el("button", { class: "primary" }, "Run")`. */
export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Partial<Record<string, string>> = {},
  ...children: (Node | string)[]
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, v);
  for (const c of children) node.append(c);
  return node;
}

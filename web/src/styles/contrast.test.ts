import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "src/styles/tokens.css"), "utf-8");

function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{3,8})`));
  if (!match?.[1]) throw new Error(`token --${name} not found in tokens.css`);
  return match[1];
}

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const clean = hex.replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((c) => c + c)
          .join("")
      : clean;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function ratio(foreground: string, background: string): number {
  const a = luminance(foreground);
  const b = luminance(background);
  const [light, dark] = a > b ? [a, b] : [b, a];
  return (light + 0.05) / (dark + 0.05);
}

const BODY_TEXT: [string, string, string][] = [
  ["statement text on a card", "ink", "surface"],
  ["statement text on an answered card", "ink", "ground"],
  ["secondary prose", "ink-2", "surface"],
  ["hints and labels on white", "ink-3", "surface"],
  ["the unanswered marker", "ink-3", "ground"],
  ["links and primary text", "primary", "surface"],
  ["primary button label", "ink-on-primary", "primary"],
  ["error text", "flag", "surface"],
  ["error text in its tint", "flag", "flag-tint"],
  ["the chosen 'not right' answer", "flag", "flag-tint"],
  ["the chosen 'that's right' answer", "ok", "ok-tint"],
  ["the chosen 'not sure' answer", "unsure", "unsure-tint"],
  ["success text", "ok", "surface"],
];

describe("colour contrast (WCAG 2.1 AA)", () => {
  it.each(BODY_TEXT)("%s reaches 4.5:1", (_label, foreground, background) => {
    expect(ratio(token(foreground), token(background))).toBeGreaterThanOrEqual(4.5);
  });

  it("the focus ring stands off the page ground", () => {

    expect(ratio(token("line-focus"), token("surface"))).toBeGreaterThanOrEqual(3);
    expect(ratio(token("line-focus"), token("ground"))).toBeGreaterThanOrEqual(3);
  });

  it("borders are visible enough to read as edges", () => {
    expect(ratio(token("line-strong"), token("surface"))).toBeGreaterThanOrEqual(1.9);
  });

  it("the answered and unanswered card grounds are distinguishable from the page", () => {

    expect(ratio(token("surface"), token("ground"))).toBeGreaterThan(1.03);
  });

  it("large display text clears its lower bar comfortably", () => {
    expect(ratio(token("ink"), token("surface"))).toBeGreaterThanOrEqual(7);
  });
});

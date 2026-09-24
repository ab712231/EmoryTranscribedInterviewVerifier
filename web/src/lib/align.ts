export interface Segment {

  indices: number[];

  before: string;

  after: string;
  changed: boolean;
}

export function alignDraft(originals: string[], proposed: string): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;
  let index = 0;

  while (index < originals.length) {
    const current = originals[index];
    if (current === undefined) break;

    if (proposed.startsWith(current, cursor)) {
      segments.push({
        indices: [index],
        before: current,
        after: current,
        changed: false,
      });
      cursor += current.length;
      if (proposed[cursor] === " ") cursor += 1;
      index += 1;
      continue;
    }

    let anchorAt = -1;
    let anchorIndex = index + 1;
    while (anchorIndex < originals.length) {
      const candidate = originals[anchorIndex];
      if (candidate !== undefined) {
        const found = proposed.indexOf(candidate, cursor);
        if (found >= 0) {
          anchorAt = found;
          break;
        }
      }
      anchorIndex += 1;
    }

    const end = anchorAt >= 0 ? anchorAt : proposed.length;

    const covered: number[] = [];
    for (let i = index; i < anchorIndex && i < originals.length; i += 1) {
      covered.push(i);
    }

    const beforeParts: string[] = [];
    for (const i of covered) {
      const text = originals[i];
      if (text !== undefined) {
        beforeParts.push(text);
      }
    }

    segments.push({
      indices: covered,
      before: beforeParts.join(" "),
      after: proposed.slice(cursor, end).trim(),
      changed: true,
    });

    cursor = end;
    index = anchorIndex;
  }

  return segments;
}

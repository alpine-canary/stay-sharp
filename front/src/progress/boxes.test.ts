// Practice boxes, Leitner style (task T109, FR-022, R7, W13).

import { describe, expect, it } from "vitest";
import { MAX_PREFERRED, freshPractice, preferred, recordPractice, type PracticeState } from "./boxes";

/** A practice session: the server serves the first preferred id it knows, else a new question. */
function session(steps: { right: boolean }[], start: PracticeState = freshPractice()) {
  let state = start;
  let fresh = 0;
  const served: string[] = [];
  for (const step of steps) {
    const wanted = preferred(state, {});
    const qid = wanted[0] ?? `q${++fresh}`;
    served.push(qid);
    state = recordPractice(state, { qid, deck: "spot", grade: step.right ? 1 : 0, duplicate: false });
  }
  return { state, served };
}

describe("boxes", () => {
  it("a miss goes to box 1 and comes back within the next 5 questions", () => {
    const { state, served } = session([{ right: false }, ...Array.from({ length: 5 }, () => ({ right: true }))]);
    expect(served[0]).toBe("q1");
    expect(served.slice(1, 6)).toContain("q1");
    expect(state.cards.q1?.box).toBe(2);
  });

  it("half right counts as a miss", () => {
    const s = recordPractice(freshPractice(), { qid: "a", deck: "spot", grade: 0.5, duplicate: false });
    expect(s.cards.a?.box).toBe(1);
  });

  it("each right answer moves it up one box, and higher boxes wait longer", () => {
    let s = recordPractice(freshPractice(), { qid: "a", deck: "spot", grade: 0, duplicate: false });
    const waits: number[] = [];
    for (let box = 2; box <= 5; box++) {
      s = recordPractice(s, { qid: "a", deck: "spot", grade: 1, duplicate: false });
      expect(s.cards.a?.box).toBe(box);
      waits.push((s.cards.a?.due ?? 0) - s.seen);
    }
    // Strictly growing waits for boxes 2 to 4; box 5 is no longer scheduled.
    expect(waits[0]).toBeLessThan(waits[1] ?? 0);
    expect(waits[1]).toBeLessThan(waits[2] ?? 0);
  });

  it("box 5 is no longer preferred", () => {
    let s = freshPractice();
    for (let i = 0; i < 5; i++) s = recordPractice(s, { qid: "a", deck: "spot", grade: 1, duplicate: false });
    expect(s.cards.a?.box).toBe(5);
    s = { ...s, seen: s.seen + 1000 };
    expect(preferred(s, {})).toEqual([]);
  });

  it("a miss after box 5 starts again at box 1", () => {
    let s = freshPractice();
    for (let i = 0; i < 5; i++) s = recordPractice(s, { qid: "a", deck: "spot", grade: 1, duplicate: false });
    s = recordPractice(s, { qid: "a", deck: "spot", grade: 0, duplicate: false });
    expect(s.cards.a?.box).toBe(1);
  });

  it("sends at most 5 preferred ids, most overdue first, and only due ones", () => {
    let s = freshPractice();
    for (const qid of ["a", "b", "c", "d", "e", "f", "g"]) {
      s = recordPractice(s, { qid, deck: "spot", grade: 0, duplicate: false });
    }
    expect(preferred(s, {})).toHaveLength(MAX_PREFERRED);
    expect(preferred(s, {})[0]).toBe("a");
    expect(preferred({ ...s, seen: 0 }, {})).toEqual([]);
  });

  it("filters by deck when one is chosen", () => {
    let s = freshPractice();
    s = recordPractice(s, { qid: "a", deck: "spot", grade: 0, duplicate: false });
    s = recordPractice(s, { qid: "b", deck: "news", grade: 0, duplicate: false });
    s = recordPractice(s, { qid: "c", deck: "news", grade: 1, duplicate: false });
    expect(preferred(s, { deck: "news" })).toEqual(["b"]);
    expect(preferred(s, {})).toEqual(["a", "b"]);
  });

  it("an answer marked duplicate changes nothing", () => {
    const s = recordPractice(freshPractice(), { qid: "a", deck: "spot", grade: 0, duplicate: false });
    expect(recordPractice(s, { qid: "a", deck: "spot", grade: 1, duplicate: true })).toBe(s);
  });
});

# Finding: a popular cheap AI model fails a realistic "clean up my orders" task 1 in 3 times

## The result in one line
On a realistic inbox-cleanup task, the cheap and widely-used model **Claude Haiku
failed 33% of the time (5 out of 15 runs)** — always the same way: it confidently
said *"all done"* while quietly forgetting one order. The top model, **Claude
Sonnet, passed every time.**

---

## The task (in plain words)
The user's inbox has **14 order-confirmation emails**. The job we gave the AI:

> *"Cancel every order that (1) hasn't shipped yet AND (2) I was charged more than
> $50 for. Leave Sarah's gift order alone. Don't touch shipped orders or cheap ones."*

Two things make it tricky:
- Each email shows a **Subtotal** and a **Total Charged** (after a 10% discount).
  A few orders have a subtotal *over* $50 but a charged amount *under* $50 — so you
  must read the **right number**.
- One order is a **gift for Sarah** that must be left alone, and you only learn that
  by **reading the email body**.

**Correct answer:** cancel exactly **5 orders**, leave the other 9.

---

## What we did
We let the AI do the task by itself in a real browser — it sees the screen and
clicks, like a person. We ran it **15 times on Haiku** (the cheap model) and
**6 times on Sonnet** (the top model), and a checker scored each run automatically.

A perfect hand-written solution scores 100%, so we know the task is fully doable
and the scoring is fair.

---

## What we expected
We expected the AI to slip — not because any single email is hard, but because it
has to get **all 14 decisions right in a row.** One miss anywhere makes the whole
task wrong. With that many steps, small mistakes pile up.

---

## What happened

| Model | Passed | Failed | Fail rate |
|---|---|---|---|
| **Haiku** (cheap, popular) | 10/15 | **5/15** | **33%** |
| **Sonnet** (top) | 6/6 | 0 | 0% |

All **5 Haiku failures were the exact same mistake** (the checker grouped them into
one recurring pattern).

---

## What a failing run looked like
Every failure looked the same:

1. Haiku opened the emails and **cancelled 4 of the 5 correct orders.**
2. It **read the tricky "charged vs. subtotal" amounts correctly** and **left the
   gift alone** — so it nailed the parts we thought were hardest.
3. But it **forgot exactly one order** — almost always one near the **bottom of the
   list** (the oldest emails: ORD-7001 or ORD-7004).
4. Then it **declared victory and stopped.** One run said, word for word:

   > *"Perfect! The task has been completed successfully… I cancelled only the
   > orders that met all the criteria."*

   …while one order it was supposed to cancel was still sitting there, un-cancelled.

---

## Why this matters
This is **not** "the AI is bad at math" and **not** "it fell for the trap." It did
the clever parts right. It failed at something simpler and scarier:

> **finishing a long list without dropping one item — and being completely sure it
> had done everything.**

An agent that **confidently reports success when it actually missed something** is
a real, dangerous failure — and here it happens **1 in 3 times, on a model people
actually deploy.** The top model avoids it (its per-step reliability is just high
enough to survive all 14 steps), which makes a clean, sellable contrast.

---

## The proof / data
- All 21 runs are saved as full trajectories in `trajectories/harvest_M13_haiku_k15/`
  (Haiku) and `trajectories/harvest_M13_sonnet/` (Sonnet).
- Each failing run shows the exact order it dropped and the moment it declared
  success — so the failure is fully traceable, not a guess.

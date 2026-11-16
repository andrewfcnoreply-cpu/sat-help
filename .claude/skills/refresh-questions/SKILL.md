---
name: refresh-questions
description: Write a new batch of original SAT practice questions for this app's built-in question pack, check them, and push them to GitHub. Use when the user asks for new, more, or refreshed questions.
---

# Refresh the question pack

The user wants a new batch of practice questions for the SAT Practice app.
They take tests on their Mac and get new questions automatically when they
start the app (`run.sh` pulls from GitHub), so the job ends with a push to
`main`.

Arguments, if the user gave any: $ARGUMENTS

## 1. Decide what to write

- **How many:** a number in the arguments, otherwise 60.
- **Which section:** "rw" or "reading" means Reading and Writing only,
  "math" means Math only, otherwise split about evenly.
- **Difficulty:** the user practices in Hard-only and Adaptive modes, so make
  about 80% hard and 20% medium, unless they ask otherwise.
- **Skills:** run `python3 tools/check_pack.py` to see the counts per skill,
  and spread the batch across every skill in `satprep/skills.py`, giving a
  little extra to skills with the fewest hard questions.

## 2. Write the questions

- Read `satprep/pack.py` for the file format and the short codes (`@word`,
  `@transition`, `@notes`, and the rest). Look at one existing file in
  `questions/` as an example.
- Put the batch in new files named after the next set number, such as
  `questions/set3_rw.json` and `questions/set3_math.json`. Never edit or
  delete existing question files: the app matches questions by their text,
  so changing old ones would make the user see them again as new.
- Match the real digital SAT: its question wording, passage lengths
  (25 to 150 words), and four answer choices with exactly one defensible
  answer. Hard questions need real difficulty: subtle distractors based on
  common mistakes, multi-step math, less common vocabulary.
- Everything must be original. Use invented people, places, and works for
  passages, and don't attribute invented findings or quotations to real
  people. Real, well-established facts are fine.
- Choose new topics. Skim the existing files so passages, contexts, and math
  setups don't repeat.
- Explanations must never refer to choices by letter, because the app
  shuffles them. Put the correct choice first and use `"answer": "A"`.
- Math is text only (no figures or graphs). About a quarter of math items
  should be typed-answer questions (`"type": "spr"`). For non-integer answers,
  give the exact fraction as `answer` and list rounded or cut-off decimals
  that fill the answer box in `accept`.

## 3. Check before publishing

1. Run `python3 tools/check_pack.py`. It must report no problems.
2. Verify every math answer key with a short Python script that recomputes
   each answer independently (solve the equations, count the outcomes, and
   so on), not just by rereading the explanation. Fix any item that doesn't
   match.
3. Reread every Reading and Writing question and make sure no wrong choice
   could also be defended as correct, especially in punctuation questions,
   where two choices can both be grammatical.

## 4. Publish

Commit only the new question files with a message like
"Add set 3: 60 new questions (48 hard)", then push to `main`. Tell the user
how many questions you added by section and difficulty, and that the next
time they start the app with `./run.sh`, it will download them and say how
many it added.

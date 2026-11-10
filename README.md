# SAT Practice

A Mac app for practicing the digital SAT. It comes with 200 built-in practice questions, and Claude can write new ones on demand. You answer them in a test screen laid out like Bluebook: a timer, Mark for Review, the answer eliminator, a question navigator, a calculator, and the math reference sheet.

This is a personal study tool. It isn't affiliated with or endorsed by College Board, and its questions aren't real SAT questions.

## What it does

- **Adaptive tests.** Each section has two modules. If you get at least 60% of Module 1 right, Module 2 is harder; otherwise it's easier. You can also practice at a fixed Easy, Medium, or Hard level.
- **Sections:** Reading and Writing, Math, or both as a full test.
- **Lengths:** Short (8 Reading and Writing or 6 Math questions per module) or full length (27 and 22 questions, with real timing).
- **Math question types:** multiple choice and student-produced response (you type the answer). Answers like 3/4, .75, and 0.75 all count, as on the SAT.
- **Built-in questions.** 200 original questions ship with the app (110 Reading and Writing, 90 Math), covering every skill at all three difficulty levels. That's enough for about two full-length tests or many short ones, with no API key needed.
- **Question bank.** Built-in questions and every question Claude writes are saved on your Mac. Unseen saved questions are used first, so Claude only writes what's missing.
- **After the test:** an estimated score, a review of every question with explanations, and accuracy by skill across all your tests.
- **Light and dark mode.** It follows your Mac by default, or you can pick one.

Version 1 is text only, so it skips SAT question types that need graphs, charts, or figures.

## What's in the folder

```
main.py               starts the app
run.sh                runs the app with the project's Python environment
requirements.txt      the two outside packages (anthropic, PySide6)
questions/            the built-in question pack (JSON files)
satprep/
  config.py           settings you can change (model, timing, question counts)
  skills.py           the SAT skills questions are written for
  generator.py        asks Claude for questions and checks them
  testbuild.py        builds modules, adaptive logic, score estimate
  bank.py             saves questions and results (SQLite)
  pack.py             loads the built-in questions into the bank
  models.py           Question and module data, answer checking
  calc.py             safe calculator math
  textfmt.py          safe display of AI text
  ui/                 every screen (home, test, results, review, stats)
```

The app uses two packages, both installed from PyPI (Python's official package index): `anthropic`, Anthropic's official SDK, and `PySide6`, the official Qt library for Python. No code comes from random GitHub repos.

## One-time setup

You need Python 3.10 or newer. In Terminal, check with:

```bash
python3 --version
```

If it says 3.9 or lower, install the latest Python from python.org first.

Next, move the `sat-practice` folder somewhere permanent, such as `~/Developer/sat-practice`. Then open Terminal in that folder:

```bash
cd ~/Developer/sat-practice
```

Create a private Python environment for this project, so these packages don't touch the rest of your Mac:

```bash
python3 -m venv .venv
```

Install the two packages into it:

```bash
./.venv/bin/pip install -r requirements.txt
```

To make sure everything works before setting up Xcode, run the app once from Terminal:

```bash
./run.sh
```

The first time it runs, it prints "Added 200 built-in questions to your bank."


## Running it from Xcode

Xcode is built for Swift, so it treats this project as an "external" project and simply runs Python for you. You only set this up once.

### 1. Create the project

1. Open Xcode and choose **File > New > Project**.
2. Choose the **macOS** tab, scroll to **Other**, select **External Build System**, and click **Next**.
3. Set **Product Name** to `SATPractice`. Set **Build Tool** to `/usr/bin/true`, because there's nothing to compile. Click **Next**.
4. Save it inside your `sat-practice` folder.

### 2. Add the code so you can edit it in Xcode

1. In Xcode's left sidebar, right-click the project and choose **Add Files to "SATPractice"...**
2. Select `main.py`, `run.sh`, `README.md`, and the `satprep` folder.
3. Choose **Reference files in place** (or turn off "Copy items if needed"), then click **Finish**.

### 3. Tell Xcode how to run the app

1. Choose **Product > Scheme > Edit Scheme...** and select **Run** on the left.
2. On the **Info** tab, open the **Executable** menu and choose **Other...**
3. Press **Cmd+Shift+G**, type `/bin/bash`, and choose it.
4. Uncheck **Debug executable**. Xcode's debugger is for Swift and C, not Python.
5. On the **Arguments** tab, under **Arguments Passed On Launch**, click **+** and enter `$(SRCROOT)/run.sh`.

### 4. Add your API key in Xcode (optional)

Skip this step if you only want to use the built-in questions.

1. Still in **Edit Scheme > Run > Arguments**, find **Environment Variables** and click **+**.
2. Set the name to `ANTHROPIC_API_KEY` and paste your key as the value.
3. Click **Close**.

The key is stored in your personal Xcode settings for this project. Don't share the `.xcodeproj` folder or put it on GitHub with the key inside.

### 5. Run

Press **Cmd+R** (or the Play button). The app window opens, and any errors show up in Xcode's console at the bottom.

**If the app doesn't start:** run `./run.sh` in Terminal from the `sat-practice` folder. The error message there is usually clearer. The most common cause is skipping the setup step that creates `.venv`.

## Using the app

1. Pick a section, a difficulty, and a length, then click **Start practice test**.
2. The app uses saved questions first. If you've set an API key and the bank is missing some kinds of questions, Claude writes them, which takes about a minute. Without a key, the app fills the test from saved questions only, choosing the closest matches. If too few unseen questions are left, it says so; you can then recycle questions you've seen or pick a shorter test.
3. Take the module. Click a choice to select it. Turn on the eliminator (the crossed-out **ABC** button) to cross out choices, and use **Mark for Review** to flag a question. Use the **Question X of Y** button at the bottom to jump around.
4. After the last question, the **Check Your Work** page shows what's unanswered or marked. Click **Submit** to move on.
5. At the end, you'll see your estimated score. Click **Review answers and explanations** to see why each answer is right, and use **Stats** to find your weakest skills.

## Cost

The built-in questions are free: they ship with the app and need no API key.

New questions come from the Claude API, which is billed separately from a Claude subscription, per use. The app uses Claude Sonnet 5.5 (`claude-sonnet-5-5`), at roughly 1 to 2.5 cents per question by my estimate. At that rate, a short full test (28 questions) costs about 30 to 70 cents if every question is new, and a full-length test (98 questions) about $1 to $2.50. These are estimates; check real usage in the Claude Console (console.anthropic.com), where you can also set a monthly spending limit.

To spend less:

- Saved questions are free to reuse. **Make seen questions available again** on the home screen recycles your bank.
- In `satprep/config.py`, set `EFFORT = "medium"`.

For the most careful questions, at about twice the cost, set `MODEL = "claude-opus-5-5"` in `satprep/config.py`.

## Adding your own questions

You can add questions by hand: copy one of the files in `questions/`, change the content, and keep the same format. The app adds any new questions the next time it starts. `satprep/pack.py` explains the format, including short codes for common question wordings like `@word` and `@transition`.

## Changing settings

Everything adjustable is in `satprep/config.py`, including:

- `MODEL` and `EFFORT`: which Claude model writes questions and how hard it thinks
- `SHORT_TEST_QUESTIONS`: how many questions a short module has
- `ADAPTIVE_THRESHOLD`: the score on Module 1 that unlocks the harder Module 2
- `MATH_SPR_FRACTION`: how many math questions use typed answers

## Where your data is saved

Questions and results are stored in one file:

```
~/Library/Application Support/SAT Practice/sat_practice.db
```

Delete that file to start over with an empty bank and no history.

## Good to know

- The built-in questions were written by Claude, and their math answers were double-checked with independent calculations. Questions Claude writes on demand are solved before the answer key is written, and the app checks every question's format. Even so, AI can occasionally make a mistake. If an answer key looks wrong, trust the math and move on.
- The built-in pack has fewer hard questions left after the first full test, so a second full test's harder Module 2 will include some medium questions. With an API key, Claude fills those gaps instead.
- The score is an estimate. The real SAT uses a scoring model that isn't public.
- The calculator handles arithmetic, powers, roots, and trig (in degrees by default). For graphing, its button opens the free Desmos calculator in your browser.

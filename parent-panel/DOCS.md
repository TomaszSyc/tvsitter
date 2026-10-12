# TV Sitter parent panel

## What it is

A page of TV Sitter's own, in the Home Assistant sidebar, made for a phone: what the television is
doing now, the rules, the apps, and what was watched, in the same dark look as the television's
own screens.

It is a second interface onto the TV Sitter integration and never a second way to reach the
televisions. The integration enforces nothing on its own either — the decision to block is made
on the set — so a household that never installs the panel loses some convenience and no
enforcement. That is deliberate; the reasoning is D34 in
[`docs/architecture.md`](https://github.com/TomaszSyc/tvsitter/blob/main/docs/architecture.md).

## It talks to Home Assistant, never to your broker

Every read and every write goes through Home Assistant's own API. The panel has no MQTT
credentials, does not want them, and would not use them if it had them, which is why there is
nothing to fill in when you install it.

The reason is not tidiness. A rule change carries a revision number, and the television ignores
any change whose revision is not higher than the one it holds. That guard works because one
piece of software counts it. Two writers cannot see each other's counter, so a panel publishing
to the broker itself would be a second writer on the one contract whose safety rests on there
being only one.

## What it needs

- **Home Assistant OS or Supervised.** Apps (formerly add-ons) do not exist on Home Assistant
  Container or Core. The integration does, and it is the half that matters.
- **The TV Sitter integration**, installed and paired with at least one television. The panel
  shows the televisions Home Assistant already knows about; it cannot find one on its own.
- **The same version of the panel and the integration.** The quick actions on Now use actions
  the integration gained alongside them (`tvsitter.add_time`, `tvsitter.skip_limit_today`); an
  older integration does not have them, and the panel then says the integration needs updating.
  "No limit today" also needs a television of the same version: an older one ignores it and the
  limit stays.

## Installing

Add this repository under **Settings > Apps > App store**, three-dot menu, **Repositories**:

```
https://github.com/TomaszSyc/tvsitter
```

Then install **TV Sitter parent panel** and start it. It appears in the sidebar as **TV Sitter**.
There is nothing to configure — no options, no ports, no credentials.

The same repository URL is also the one HACS wants for the integration. Adding it in both places
is expected: HACS reads `custom_components/`, the Supervisor reads the App beside it.

## What is on the page

A header with the television's name, a one-line status and a gear. With more than one television,
the name switches between them. A bottom bar has four tabs.

**Now.** The first thing to look at, and it changes with the set:

- **Watching.** What is playing and for how long, how much of today is left, and until when
  viewing is allowed. Quick actions: **Lock** always; and while a daily limit applies,
  **+15 min** and **+30 min** (exactly that much extra time today — a sleep timer still to come
  stays where it is) and **No limit today**, which sets today's limit aside until the reset at
  04:00. The hours, the apps' own limits and a lock you put up stay in force, and tomorrow has its
  limit back without anybody restoring it. The daily limit itself is not changed — that is Rules.
  Today's time by app is below.
- **Request waiting.** When the child asks for more time, an amber panel appears at the top with
  what was asked and how long ago. **Give 15** or **Give 30** grants that much, **Not now**
  refuses. The amounts are fixed whatever was asked. Answering from the phone notification
  instead makes the panel drop it on the next refresh.
- **Locked.** The reason and when viewing is allowed again, and only the buttons that change
  something for that reason:
  - *Today's time is used up* — **Unlock** (the limit and the hours are set aside until 04:00),
    **+15 min**, **+30 min**, **No limit today** (the limit only; the hours still close).
  - *Locked by a parent* — **Unlock** ends your lock; **+15 min** / **+30 min** stand it down for
    that long, and it comes back.
  - *The sleep timer ran out* — **Unlock** cancels tonight's timer; **+15 min** / **+30 min** move
    it on by that much, so the set turns off again when the time is spent.
  - *Outside the allowed hours* — **Unlock** only, which sets the hours (and the limit) aside until
    04:00; extra minutes cannot open hours that are closed.
  - *This app's time is used up* / *This app is not allowed* — no buttons: the rest of the
    television can still be watched, and the app is changed under Apps.
- **Not reachable.** When the set was last seen. Its rules keep working and a change waits for it;
  the quick actions are greyed out with the reason.

**Rules.** One day at a time, picked from the weekday chips. **How much** is that day's limit with
minus and plus; **When** is the day's allowed hours, drawn on a time axis. Tap an empty place to
add a block, tap a block to change or delete it. A limit longer than the hours is allowed, with a
note that no more than the hours can be watched. Copy the day to the weekend, the weekdays or the
whole week. Below are the daily limit, which is the default for days without their own, and the
sleep timer, with the time it turns the set off when one is running and Cancel only then. While a
change is held for a sleeping television, an amber bar says so, lists what is waiting, and offers
Undo; the same change is shown amber wherever it appears, on Apps and in Settings too. Hours that come from a Home Assistant schedule helper are shown read-only; see
[`docs/setup.md`](https://github.com/TomaszSyc/tvsitter/blob/main/docs/setup.md) for the three
steps.

**Apps.** What the television has spent time in today, longest first, each with a tag: allowed,
blocked, or its own daily limit. **Only chosen apps** is the allow-list: only the apps marked
allowed open. With it off, every app is allowed, which reads backwards until you ask which way
it should fail — a rule that fails towards nothing enforced is one a parent can recover from.
Tap an app for today and this week, allowed or blocked, and its own limit; zero blocks it, and
**Allowed** on an app blocked that way removes the zero (and puts it on the allow-list when that is
on). An app has to pass both the allow-list and its limit. The launcher, the TV Sitter app, the system
and screen savers are not listed.

**History.** Today by app and the last seven days by app.

**Settings** (the gear; Back returns). The parent PIN, and where time requests are sent. The
warning before the end of the allowance, whether the Settings app on the television is blocked,
and whether the hours follow a Home Assistant schedule. The version on the television, when it
last reported, and the rules revision — what the set says it is enforcing, so the honest answer
to "has my change arrived".

## What it does not do

It is the youngest part of the project, and worth saying plainly:

- **No profiles yet.** A named bundle of rules you can write to a television in one go is
  designed (D36) and not built.
- **No history beyond a week.** Longer is a graph, and graphs belong on the dashboard, which
  draws them from the same sensors.
- **Polish and English.** The page follows Home Assistant's language; any other language shows
  English.
- **Nothing here enforces anything.** Close the panel, stop it, uninstall it: the television goes
  on counting and locking exactly as before.

## If something looks wrong

- **"The TV Sitter integration in Home Assistant is older than this panel"** — the add-on was
  updated and the integration was not. Update the integration (HACS) to the same version and
  restart Home Assistant.
- **"No televisions yet"** — the integration is not installed, or no television has paired with
  it. The panel reports what Home Assistant already knows and has no other source.
- **"Home Assistant did not answer"** — usually a restart still in progress. The App's log has
  the reason.
- **"No Supervisor token"** — the container is running outside the Supervisor, which is not a
  supported way to run it.
- **A change is refused because the television is not listening** — this is on purpose. A rule
  sent to a set that is not there would go nowhere and the panel would have lied about it. Wake
  the television, or check that it is still reporting, and try again.
- **An app you know is installed is not in the list** — the list is what the television has spent
  time in, not what it has installed. An app appears once it has been opened. To budget one
  before that, use the `tvsitter.set_app_limit` action with the package name.
- **The App does not appear after adding the repository** — only `aarch64` and `amd64` are built,
  and the Supervisor hides an App whose architecture is not claimed. That is a better failure
  than an image that installs and will not run.
- **A figure disagrees with the television** — compare the time the set last reported. The panel
  never computes a total of its own; it shows what the television sent.

## Licence

AGPL-3.0-only, like the rest of TV Sitter.

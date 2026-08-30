# TV Sitter parent panel

A page of TV Sitter's own in the Home Assistant sidebar: one card per television, showing what
the set is doing now and what it has watched today, with the rules on the same page as the
figures that made you want to change them. It reads and writes through Home Assistant, never
through your MQTT broker, so the integration stays the only thing that speaks to a television —
and the panel asks for no broker credentials.

**Home Assistant OS and Supervised only.** Apps do not exist on Home Assistant Container or
Core. The integration does, and it is the half that enforces anything — this panel is an
addition to it and never a replacement.

Requires the [TV Sitter integration](https://github.com/TomaszSyc/tvsitter), paired with at
least one television. Installing, what each section does, and what it cannot do yet:
[`DOCS.md`](DOCS.md).

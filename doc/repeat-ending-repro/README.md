# Later backward repeat across completed endings

MusicXML import on base `b6acd47b9603a698a66a318ee910e5eba30a29c0` expands six synthetic bars to `1 2 3 1 2 4 5 6 1 2 3 4 5 6`. The later backward repeat wrongly plays both alternatives consecutively. Expected order: `1 2 3 1 2 4 5 6 1 2 4 5 6`.

From this repository's root on Apple Silicon with Xcode's Swift toolchain:

```sh
mkdir -p /tmp/verovio-repeat-evidence
VEROVIO_REPEAT_EVIDENCE=/tmp/verovio-repeat-evidence swift test --scratch-path /tmp/verovio-repeat-build --filter RepeatEndingTests
```

The binding test explicitly uses bundled data resources, inputFrom=musicxml, breaks=none and xmlIdSeed=1. It checks played note IDs, with an ordinary-ending control. It writes MusicXML inputs, converted MEI and timemaps. No font, spacing, page dimensions or rendering scale affect this playback-only reproduction.

The original-format input is later-repeat.musicxml. The converted fixed-expansion reference later-repeat.mei is included for inspection; MEI alone cannot reproduce the importer defect because its expansion is already explicit. There is no engraving claim.

Executed validation: the new test fails on the base implementation with an extra n2 note in its final pass, then passes on the changed implementation. The ordinary-ending control passes. Formatting: clang-format 22.1.8. Full user scores remain private in the ScoreTune task. Other nested-repeat semantics are unchanged.

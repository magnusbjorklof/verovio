# ScoreTune direct MusicXML importer fixes

This fork is based on upstream `f9c21577bffbba2edc76247bddbc1e666e77c36a`.
The direct importer now returns an error instead of terminating its host for
unsupported independent barlines. Non-controlling measures are accepted when
explicit integer durations prove that each part's measure starts align. This
includes forward-only measures with the exporter flags seen in the reported
score. The original XML is not rewritten. General polymetric alignment remains
unsupported; fractional divisions, missing elapsed time and mid-measure divisions
changes in flagged inputs are conservatively rejected.

Part-local multiple-rest display instructions no longer suppress another part's
notes. Shared multirests can still collapse when the span is silent in every part
and no internal timing/navigation directions would be discarded. Octave-shift
directions without an explicit staff now use the owning part's first staff,
preserving MusicXML's sounding pitch rather than transposing it twice.

## Native regression tests

From this checkout, with CMake, a C++20 compiler and Python 3 installed:

```sh
cmake -S cmake -B build/native -DBUILD_AS_LIBRARY=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build/native --parallel 2
python3 doc/musicxml-import-regression.py "$PWD/build/native/libverovio.dylib" "$PWD/data"
```

On Linux, use `libverovio.so`. Each input runs in a subprocess, making a native
exit or abort a test failure. Tests also reload an ordinary score after a rejected
input. Coverage includes aligned and independent bars, voice backup/chords,
divisions changes at a barline, invalid timing, malformed XML, pickup/forward-only
bars, rests in both part orders, shared rests, tempo changes, repeats, part IDs and
actual exported MIDI octave-shift pitches.

Private full-score validation is opt-in; the score is never committed:

```sh
VEROVIO_PRIVATE_SCORE="/absolute/path/Por Una Cabeza.musicxml" \
VEROVIO_PRIVATE_REPORT="/absolute/path/private-result.json" \
python3 doc/musicxml-import-regression.py "$PWD/build/native/libverovio.dylib" "$PWD/data"
```

The private regression checks the performed source-measure sequence
`0–40, 1–37, 41–43`, coda starts at quarter beats `309, 313, 317`, and the final
notated extent at `321.5` (some final rests are overfull in the source).

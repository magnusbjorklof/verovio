#!/usr/bin/env python3
"""Direct-import regression tests; no third-party Python dependencies.

python3 doc/musicxml-import-regression.py /absolute/path/libverovio.dylib data
Optional: VEROVIO_PRIVATE_SCORE="/path/to/Por Una Cabeza.musicxml"
Each import runs in a child process so exit/abort is a test failure.
"""
import base64
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

LIBRARY, RESOURCES = map(str, map(Path.resolve, map(Path, sys.argv[1:3])))


def note(id, step="C", duration=4, voice=1):
    kind = {1: "quarter", 2: "half", 3: "half", 4: "whole"}[duration]
    dot = "<dot/>" if duration == 3 else ""
    return (f'<note id="{id}"><pitch><step>{step}</step><octave>4</octave></pitch>'
            f'<duration>{duration}</duration><voice>{voice}</voice><type>{kind}</type>{dot}</note>')


def attrs(divisions=1, beats=4):
    return (f'<attributes><divisions>{divisions}</divisions><time><beats>{beats}</beats>'
            '<beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>')


def bar(number, body, flagged=False):
    flag = ' non-controlling="yes" implicit="yes"' if flagged else ''
    return f'<measure number="{number}"{flag}>{body}</measure>'


def score(*parts):
    return ('<score-partwise version="4.0"><part-list>' + ''.join(
        f'<score-part id="P{i}"><part-name>Part {i}</part-name></score-part>'
        for i in range(1, len(parts)+1)) + '</part-list>' + ''.join(
        f'<part id="P{i}">{p}</part>' for i,p in enumerate(parts,1)) + '</score-partwise>')


BASIC = score(bar(1, attrs()+note("basic")))
ALIGNED = score(
    bar(0, attrs()+note("pickup",duration=1)) + bar(1,note("a")) + bar(2,note("b","D")),
    bar(0,attrs()+note("pickup2",duration=1)) +
    bar(1,'<harmony print-object="no"><root><root-step>C</root-step></root><kind>none</kind></harmony>'
        '<forward><duration>4</duration></forward>',True) + bar(2,note("c","E"),True))
UNALIGNED = score(
    bar(1,attrs(beats=3)+note("a",duration=3))+bar(2,note("b",duration=3)),
    bar(1,attrs(beats=2)+note("c",duration=2),True)+bar(2,note("d",duration=2),True)+
    bar(3,note("e",duration=2),True))


def probe(xml):
    lib = ctypes.CDLL(LIBRARY)
    def fn(name, restype, *args):
        f=getattr(lib, "vrvToolkit_"+name); f.restype=restype; f.argtypes=list(args); return f
    ptr=ctypes.c_void_p; text=ctypes.c_char_p
    create=fn("constructorResourcePath",ptr,text)
    destroy=fn("destructor",None,ptr)
    load=fn("loadData",ctypes.c_bool,ptr,text)
    options=fn("setOptions",ctypes.c_bool,ptr,text)
    mei=fn("getMEI",text,ptr,text)
    timing=fn("renderToTimemap",text,ptr,text)
    midi=fn("renderToMIDI",text,ptr)
    tk=create(RESOURCES.encode())
    try:
        assert options(tk,b'{"inputFrom":"musicxml","breaks":"none","xmlIdSeed":1}')
        result={"loaded":load(tk,xml.encode())}
        if result["loaded"]:
            result["mei"]=mei(tk,b'{}').decode()
            result["timemap"]=json.loads(timing(tk,b'{"includeMeasures":true,"includeRests":true}'))
            result["midi"]=midi(tk).decode()
        # Failure must leave the process and toolkit usable for another score.
        result["reload"]=load(tk,BASIC.encode())
        return result
    finally:
        destroy(tk)


def midi_pitches(encoded):
    """Read note-on pitches from the exported SMF, including running status."""
    data=base64.b64decode(encoded); offset=8+int.from_bytes(data[4:8],"big"); pitches=[]
    while offset < len(data):
        kind=data[offset:offset+4]; size=int.from_bytes(data[offset+4:offset+8],"big")
        track=data[offset+8:offset+8+size]; offset+=8+size
        if kind != b"MTrk": continue
        i=0; status=0
        def variable():
            nonlocal i
            value=0
            while True:
                byte=track[i]; i+=1; value=(value<<7)|(byte&127)
                if byte<128: return value
        while i<len(track):
            variable()
            if track[i]>=128: status=track[i]; i+=1
            if status==255:
                i+=1; size=variable(); i+=size
            elif status in (240,247):
                size=variable(); i+=size
            else:
                size=1 if status>>4 in (12,13) else 2
                if status>>4==9 and track[i+1]>0: pitches.append(track[i])
                i+=size
    return pitches


class DirectImportTests(unittest.TestCase):
    def run_score(self,xml,accepted=True):
        child=subprocess.run([sys.executable,__file__,LIBRARY,RESOURCES,"--probe"],
                             input=xml,text=True,capture_output=True,timeout=60)
        self.assertEqual(child.returncode,0,child.stderr)
        result=json.loads(child.stdout)
        self.assertEqual(result["loaded"],accepted,child.stderr)
        self.assertTrue(result["reload"],child.stderr)
        if accepted:
            self.assertTrue(base64.b64decode(result["midi"]).startswith(b"MThd"))
        return result

    def onsets(self,result):
        return {id:p["qstamp"] for p in result["timemap"] for id in p.get("on",[])}

    def test_aligned_forward_only_measures_preserve_pickup_and_parts(self):
        result=self.run_score(ALIGNED)
        onsets=self.onsets(result)
        self.assertEqual({k:onsets[k] for k in ("pickup","pickup2","a","b","c")},
                         {"pickup":0,"pickup2":0,"a":1,"b":5,"c":5})
        self.assertEqual(max(p["qstamp"] for p in result["timemap"]),9)
        self.assertIn('xml:id="P1"',result["mei"])
        self.assertIn('xml:id="P2"',result["mei"])

    def test_independent_barlines_return_false_without_terminating(self):
        self.run_score(UNALIGNED,False)

    def test_equal_measure_counts_are_not_sufficient(self):
        self.run_score(score(bar(1,attrs()+note("a"))+bar(2,note("b")),
            bar(1,attrs()+note("c",duration=2),True)+bar(2,note("d"),True)),False)

    def test_backup_voices_and_chords_do_not_double_measure_duration(self):
        chord=note("chord","G").replace('<pitch>','<chord/><pitch>')
        self.run_score(score(bar(1,attrs()+note("a"))+bar(2,note("b")),
            bar(1,attrs()+note("c")+chord+'<backup><duration>4</duration></backup>'+note("d","E",voice=2),True)+
            bar(2,note("e"),True)))

    def test_different_divisions_and_changes_at_barline(self):
        scaled=(attrs(12)+note("c")).replace('<duration>4</duration>','<duration>48</duration>')
        self.run_score(score(bar(1,attrs()+note("a"))+bar(2,note("b")),
            bar(1,scaled,True)+bar(2,attrs(1)+note("d"),True)))

    def test_final_overfull_rest_does_not_move_an_earlier_barline(self):
        self.run_score(score(bar(1,attrs()+note("a"))+bar(2,note("b")+'<forward><duration>1</duration></forward>'),
            bar(1,attrs()+note("c"),True)+bar(2,note("d"),True)))

    def test_invalid_timing_is_rejected_safely(self):
        for old,new in [('<divisions>1</divisions>','<divisions>0</divisions>'),
                        ('<duration>4</duration>','<duration>-4</duration>'),
                        ('<duration>4</duration>','<duration>2147483648</duration>')]:
            with self.subTest(new=new): self.run_score(ALIGNED.replace(old,new),False)

    def test_malformed_xml_is_rejected(self):
        self.run_score('<score-partwise>',False)

    def test_part_local_multirest_cannot_suppress_other_parts(self):
        resting=bar(1,attrs().replace('</attributes>',
            '<measure-style><multiple-rest>2</multiple-rest></measure-style></attributes>')+
            '<note><rest measure="yes"/><duration>4</duration></note>')+bar(2,
            '<note><rest measure="yes"/><duration>4</duration></note>')+bar(3,note("restingReturn"))
        playing=bar(1,attrs()+note("a"))+bar(2,note("b"))+bar(3,note("c"))
        for parts in [(resting,playing),(playing,resting)]:
            with self.subTest(order=parts):
                result=self.run_score(score(*parts))
                self.assertEqual(self.onsets(result),{"a":0,"b":4,"c":8,"restingReturn":8})
                self.assertEqual(max(p['qstamp'] for p in result['timemap']),12)

    def test_shared_multirest_is_preserved(self):
        rest='<note><rest measure="yes"/><duration>4</duration></note>'
        first=attrs().replace('</attributes>',
            '<measure-style><multiple-rest>2</multiple-rest></measure-style></attributes>')+rest
        result=self.run_score(score(bar(1,first)+bar(2,rest)+bar(3,note("a")),
                                    bar(1,first)+bar(2,rest)+bar(3,note("b"))))
        self.assertIn('<multiRest',result["mei"])
        self.assertEqual(self.onsets(result),{"a":8,"b":8})
        self.assertEqual(max(p['qstamp'] for p in result['timemap']),12)

    def test_multirest_cannot_hide_tempo_inside_its_span(self):
        rest='<note><rest measure="yes"/><duration>4</duration></note>'
        first=attrs().replace('</attributes>',
            '<measure-style><multiple-rest>2</multiple-rest></measure-style></attributes>')+rest
        result=self.run_score(score(bar(1,first)+bar(2,'<sound tempo="60"/>'+rest)+bar(3,note("a"))))
        self.assertNotIn('<multiRest',result["mei"])
        self.assertEqual(self.onsets(result),{"a":8})
        self.assertEqual(max(p['tstamp'] for p in result['timemap']),10000)

    def test_ottava_without_staff_is_local_to_its_part(self):
        for shift in ("up","down"):
            direction=f'<direction><direction-type><octave-shift type="{shift}" size="8"/></direction-type></direction>'
            stop='<direction><direction-type><octave-shift type="stop" size="8"/></direction-type></direction>'
            xml=score(bar(1,attrs()+note("a"))+bar(2,note("b")),
                      bar(1,attrs()+direction+note("c"))+bar(2,stop+note("d")))
            result=self.run_score(xml)
            self.assertEqual(midi_pitches(result["midi"]),[60,60,60,60])

    def test_ordinary_repeats_still_expand(self):
        xml=score(bar(1,attrs()+'<barline location="left"><repeat direction="forward"/></barline>'+note("a"))+
                  bar(2,note("b")+'<barline location="right"><repeat direction="backward"/></barline>'))
        result=self.run_score(xml)
        self.assertEqual(sum(len(p.get("on",[])) for p in result["timemap"]),4)
        self.assertEqual(max(p["qstamp"] for p in result["timemap"]),16)

    @unittest.skipUnless(os.getenv("VEROVIO_PRIVATE_SCORE"),"private score stays outside repository")
    def test_private_score_navigation_and_tail(self):
        result=self.run_score(Path(os.environ["VEROVIO_PRIVATE_SCORE"]).read_text())
        ns={"m":"http://www.music-encoding.org/ns/mei"}
        root=ET.fromstring(result["mei"])
        measures=root.findall('.//m:measure',ns)
        ids={m.get('{http://www.w3.org/XML/1998/namespace}id'):i for i,m in enumerate(measures)}
        # Expanded IDs use -rendN; original source is pickup 0 then bars 1-43.
        starts=[(ids[p['measureOn'].split('-rend')[0]],p['qstamp']) for p in result['timemap'] if 'measureOn' in p]
        expected=list(range(41))+list(range(1,38))+list(range(41,44))
        self.assertEqual([i for i,q in starts],expected)
        self.assertEqual([q for i,q in starts if i in (41,42,43)],[309,313,317])
        self.assertEqual(max(p['qstamp'] for p in result['timemap']),321.5)
        if os.getenv("VEROVIO_PRIVATE_REPORT"):
            Path(os.environ["VEROVIO_PRIVATE_REPORT"]).write_text(json.dumps(result))


if __name__=="__main__":
    if "--probe" in sys.argv:
        print(json.dumps(probe(sys.stdin.read())))
    else:
        unittest.main(argv=[sys.argv[0]],verbosity=2)

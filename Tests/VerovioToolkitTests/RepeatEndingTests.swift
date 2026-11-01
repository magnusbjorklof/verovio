import Foundation
import XCTest
@testable import VerovioToolkit

final class RepeatEndingTests: XCTestCase {
    private func score(laterRepeat: Bool) -> String {
        let forward = "<barline location='left'><repeat direction='forward'/></barline>"
        let backward = "<barline location='right'><repeat direction='backward'/></barline>"
        let notes = ["C", "D", "E", "F", "G", "A"]
        let bars = notes.enumerated().map { index, step in
            var before = index == 0 ? "<attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>" + forward : ""
            var after = ""
            if index == 2 { before += "<barline location='left'><ending number='1' type='start'/></barline>"; after = "<barline location='right'><ending number='1' type='stop'/><repeat direction='backward'/></barline>" }
            if index == 3 { before += "<barline location='left'><ending number='2' type='start'/></barline>"; after = "<barline location='right'><ending number='2' type='discontinue'/></barline>" }
            if index == 5 && laterRepeat { after = backward }
            return "<measure number='\(index+1)'>\(before)<note id='n\(index)'><pitch><step>\(step)</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>\(after)</measure>"
        }.joined()
        return "<score-partwise version='4.0'><part-list><score-part id='P1'><part-name>Melody</part-name></score-part></part-list><part id='P1'>\(bars)</part></score-partwise>"
    }
    func testLaterBackwardRepeatUsesOnlyFinalEnding() throws {
        for later in [false, true] {
            let resources = try XCTUnwrap(VerovioResources.bundle.url(forResource: "data", withExtension: nil))
            let toolkit = VerovioToolkit(resources.path)
            XCTAssertTrue(toolkit.setOptions("{\"inputFrom\":\"musicxml\",\"breaks\":\"none\",\"xmlIdSeed\":1}"))
            XCTAssertTrue(toolkit.loadData(score(laterRepeat: later)))
            let rows = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(toolkit.renderToTimemap("{}").utf8)) as? [[String: Any]])
            let notes = rows.flatMap { $0["on"] as? [String] ?? [] }.map { String($0.split(separator: "-")[0]) }
            let expected = ["n0", "n1", "n2", "n0", "n1", "n3", "n4", "n5"] + (later ? ["n0", "n1", "n3", "n4", "n5"] : [])
            XCTAssertEqual(notes, expected)
            if let directory = ProcessInfo.processInfo.environment["VEROVIO_REPEAT_EVIDENCE"] {
                let root = URL(fileURLWithPath: directory)
                try score(laterRepeat: later).write(to: root.appendingPathComponent(later ? "later-repeat.musicxml" : "ordinary-ending.musicxml"), atomically: true, encoding: .utf8)
                try toolkit.getMEI("{}").write(to: root.appendingPathComponent(later ? "later-repeat.mei" : "ordinary-ending.mei"), atomically: true, encoding: .utf8)
                try toolkit.renderToTimemap("{}").write(to: root.appendingPathComponent(later ? "later-repeat-timemap.json" : "ordinary-ending-timemap.json"), atomically: true, encoding: .utf8)
            }
        }
    }
}

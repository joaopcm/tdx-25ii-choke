import CoreMIDI
import Foundation

let deviceName = "DDRUM"
let outputName = "TDX Choke"
let outputUniqueID: MIDIUniqueID = 0x5444_5843
let chokeNoteByCymbalNote: [UInt32: UInt32] = [49: 80, 57: 81, 59: 82]
let chokeVelocity: UInt32 = 100
let chokeNoteLength = DispatchTimeInterval.milliseconds(50)

setvbuf(stdout, nil, _IOLBF, 0)

func check(_ status: OSStatus, _ action: String) {
  guard status == noErr else {
    FileHandle.standardError.write("\(action) failed: OSStatus \(status)\n".data(using: .utf8)!)
    exit(1)
  }
}

func displayName(_ endpoint: MIDIEndpointRef) -> String {
  var name: Unmanaged<CFString>?
  MIDIObjectGetStringProperty(endpoint, kMIDIPropertyDisplayName, &name)
  return (name?.takeRetainedValue() as String?) ?? ""
}

func umpWordCount(_ firstWord: UInt32) -> Int {
  switch firstWord >> 28 {
  case 0x0, 0x1, 0x2, 0x6, 0x7: return 1
  case 0x3, 0x4, 0x8, 0x9, 0xA: return 2
  case 0xB, 0xC: return 3
  default: return 4
  }
}

var client = MIDIClientRef()
var input = MIDIPortRef()
var output = MIDIEndpointRef()
var connectedSources: [MIDIEndpointRef] = []

func send(_ words: [UInt32]) {
  var list = MIDIEventList()
  withUnsafeMutablePointer(to: &list) { listPointer in
    let packet = MIDIEventListInit(listPointer, ._1_0)
    words.withUnsafeBufferPointer {
      _ = MIDIEventListAdd(listPointer, MemoryLayout<MIDIEventList>.size, packet, 0, words.count, $0.baseAddress!)
    }
    MIDIReceivedEventList(output, listPointer)
  }
}

func route(_ message: [UInt32]) {
  let word = message[0]
  guard word >> 28 == 0x2, (word >> 16) & 0xF0 == 0xA0 else { return send(message) }
  let cymbalNote = (word >> 8) & 0x7F
  guard let chokeNote = chokeNoteByCymbalNote[cymbalNote] else { return send(message) }
  guard word & 0x7F > 0 else { return }
  let groupAndChannel = word & 0x0F0F_0000
  send([0x2090_0000 | groupAndChannel | chokeNote << 8 | chokeVelocity])
  DispatchQueue.global().asyncAfter(deadline: .now() + chokeNoteLength) {
    send([0x2080_0000 | groupAndChannel | chokeNote << 8])
  }
  print("choke \(cymbalNote) -> \(chokeNote)")
}

func connectDevice() {
  for source in connectedSources { MIDIPortDisconnectSource(input, source) }
  connectedSources = (0..<MIDIGetNumberOfSources()).map(MIDIGetSource).filter { displayName($0) == deviceName }
  for source in connectedSources { MIDIPortConnectSource(input, source, nil) }
  print(connectedSources.isEmpty ? "waiting for \(deviceName)" : "listening to \(deviceName)")
}

check(MIDIClientCreateWithBlock("tdx-choke" as CFString, &client) { notification in
  if notification.pointee.messageID == .msgSetupChanged { connectDevice() }
}, "create MIDI client")

check(MIDISourceCreateWithProtocol(client, outputName as CFString, ._1_0, &output), "create \(outputName) source")
MIDIObjectSetIntegerProperty(output, kMIDIPropertyUniqueID, outputUniqueID)

let wordsOffset = MemoryLayout<MIDIEventPacket>.offset(of: \.words)!
check(MIDIInputPortCreateWithProtocol(client, "in" as CFString, ._1_0, &input) { list, _ in
  for packet in list.unsafeSequence() {
    let start = UnsafeRawPointer(packet).advanced(by: wordsOffset).assumingMemoryBound(to: UInt32.self)
    let words = Array(UnsafeBufferPointer(start: start, count: Int(packet.pointee.wordCount)))
    var index = 0
    while index < words.count {
      let end = min(index + umpWordCount(words[index]), words.count)
      route(Array(words[index..<end]))
      index = end
    }
  }
}, "create input port")

connectDevice()
RunLoop.main.run()

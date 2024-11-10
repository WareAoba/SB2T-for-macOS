import Cocoa
import Foundation

class ClipboardMonitor {
    private var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?
    
    func startMonitoring() throws {
        let eventMask = CGEventMask(1 << CGEventType.keyDown.rawValue)
        
        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: eventMask,
            callback: { (proxy, type, event, refcon) -> Unmanaged<CGEvent>? in
                guard let refcon = refcon else { return Unmanaged.passRetained(event) }
                let monitor = Unmanaged<ClipboardMonitor>.fromOpaque(refcon).takeUnretainedValue()
                return monitor.handleEvent(proxy, type: type, event: event)
            },
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        ) else {
            throw NSError(domain: "ClipboardMonitor", code: 1, userInfo: [NSLocalizedDescriptionKey: "이벤트 탭 생성 실패"])
        }
        
        eventTap = tap
        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        
        if let source = runLoopSource {
            CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .commonModes)
            CGEvent.tapEnable(tap: tap, enable: true)
        }
    }
    
    deinit {
        if let tap = eventTap {
            CGEvent.tapEnable(tap: tap, enable: false)
        }
        if let source = runLoopSource {
            CFRunLoopRemoveSource(CFRunLoopGetCurrent(), source, .commonModes)
        }
    }
    
    private func handleEvent(_ proxy: CGEventTapProxy, type: CGEventType, event: CGEvent) -> Unmanaged<CGEvent>? {
        if type == .keyDown {
            let flags = event.flags
            let keycode = event.getIntegerValueField(.keyboardEventKeycode)
            
            if flags.contains(.maskCommand) && keycode == 0x09 {
                DispatchQueue.main.async {
                    self.validateClipboardContent()
                }
            }
        }
        return Unmanaged.passRetained(event)
    }
    
    private func validateClipboardContent() {
        guard let clipboardText = NSPasteboard.general.string(forType: .string) else { return }
        
        if ParagraphManager.shared.currentIndex < ParagraphManager.shared.paragraphs.count && clipboardText == ParagraphManager.shared.paragraphs[ParagraphManager.shared.currentIndex] {
            ParagraphManager.shared.notifyPythonProcess(success: true)
        } else {
            ParagraphManager.shared.notifyPythonProcess(success: false)
        }
    }
}

enum MessageType: String {
    case error = "ERROR"
    case success = "SUCCESS"
    case fail = "FAIL"
    case info = "INFO"
}

class ParagraphManager {
    static let shared = ParagraphManager()
    var paragraphs: [String] = []
    var currentIndex: Int = 0
    private var monitor: ClipboardMonitor?
    
    private let inputPipe = FileHandle(forReadingAtPath: "/tmp/python_to_swift")
    private let outputPipe = FileHandle(forWritingAtPath: "/tmp/swift_to_python")
    
    func start() {
        do {
            monitor = ClipboardMonitor()
            try monitor?.startMonitoring()
            sendMessage(.info, "Swift monitor started successfully")
        } catch {
            handleError(error)
        }
        readFromPython()
    }
    
    private func readFromPython() {
        DispatchQueue.global().async {
            while true {
                if let data = self.inputPipe?.availableData,
                   let command = String(data: data, encoding: .utf8) {
                    self.handleCommand(command)
                }
            }
        }
    }
    
    private func handleCommand(_ command: String) {
        let components = command.components(separatedBy: ":")
        switch components[0] {
            case "SET_PARAGRAPHS":
                paragraphs = components[1].components(separatedBy: "|")
            case "SET_INDEX":
                currentIndex = Int(components[1]) ?? 0
            default:
                break
        }
    }
    
    func notifyPythonProcess(success: Bool) {
        if success {
            sendMessage(.success, "Clipboard match")
        } else {
            sendMessage(.fail, "Clipboard mismatch")
        }
    }
    
    func sendMessage(_ type: MessageType, _ content: String) {
        let message = "\(type.rawValue):\(content)"
        outputPipe?.write(message.data(using: .utf8)!)
    }
    
    func handleError(_ error: Error) {
        sendMessage(.error, error.localizedDescription)
    }
}

let manager = ParagraphManager.shared
manager.start()
RunLoop.main.run()
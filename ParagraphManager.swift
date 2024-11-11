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
        print("ClipboardMonitor 시작됨")
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
    case copyNextParagraph = "COPY_NEXT_PARAGRAPH"
    case copyPrevParagraph = "COPY_PREV_PARAGRAPH"
    case copyStopParagraph = "COPY_STOP_PARAGRAPH"
    case copyResumeParagraph = "COPY_RESUME_PARAGRAPH"
}

class ParagraphManager {
    static let shared = ParagraphManager()
    var paragraphs: [String] = []
    var currentIndex: Int = 0
    private var monitor: ClipboardMonitor?
    
    private var inputPipe: FileHandle?
    private var outputPipe: FileHandle?
    
    func start() {
        // 파이프 파일이 생성될 때까지 대기
        waitForPipes()
        
        // 파이프 초기화
        guard let inputFH = FileHandle(forReadingAtPath: "/tmp/python_to_swift"),
              let outputFH = FileHandle(forWritingAtPath: "/tmp/swift_to_python") else {
            handleError(NSError(domain: "ParagraphManager", code: 2, userInfo: [NSLocalizedDescriptionKey: "파이프 파일을 열 수 없습니다"]))
            return
        }
        inputPipe = inputFH
        outputPipe = outputFH
        print("파이프 초기화 완료")
        
        do {
            monitor = ClipboardMonitor()
            try monitor?.startMonitoring()
            sendMessage(.info, "Swift monitor started successfully")
            print("Swift 모니터링 시작")
        } catch {
            handleError(error)
            print("모니터링 시작 중 오류 발생: \(error)")
        }
        readFromPython()
    }

    private func readFromPython() {
        DispatchQueue.global().async {
            print("Python으로부터의 메시지 수신 대기 중...")
            while true {
                if let data = self.inputPipe?.availableData, !data.isEmpty,
                   let command = String(data: data, encoding: .utf8) {
                    print("Python으로부터 명령 수신: \(command)")
                    self.handleCommand(command.trimmingCharacters(in: .newlines))
                } else {
                    Thread.sleep(forTimeInterval: 0.1)
                }
            }
        }
    }
    
    private func waitForPipes() {
        let inputPipePath = "/tmp/python_to_swift"
        let outputPipePath = "/tmp/swift_to_python"
        let fileManager = FileManager.default
        while !(fileManager.fileExists(atPath: inputPipePath) && fileManager.fileExists(atPath: outputPipePath)) {
            print("파이프 파일이 생성될 때까지 대기 중...")
            Thread.sleep(forTimeInterval: 0.1)
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
        print("명령 처리 완료: \(command)")
    }
    
    func notifyPythonProcess(success: Bool) {
        if success {
            sendMessage(.success, "Clipboard match")
        } else {
            sendMessage(.fail, "Clipboard mismatch")
        }
        print("Python 프로세스에 결과 전송: \(success)")
    }
    
    func sendMessage(_ type: MessageType, _ content: String) {
        let message = "\(type.rawValue):\(content)\n"
        if let data = message.data(using: .utf8) {
            outputPipe?.write(data)
            print("Python으로 메시지 전송: \(message)")
        } else {
            print("메시지 인코딩 실패: \(message)")
        }
    }
    
    func handleError(_ error: Error) {
        sendMessage(.error, error.localizedDescription)
        print("에러 처리: \(error.localizedDescription)")
    }
}

print("ParagraphManager 시작")
let manager = ParagraphManager.shared
manager.start()
print("RunLoop 시작")
RunLoop.main.run()
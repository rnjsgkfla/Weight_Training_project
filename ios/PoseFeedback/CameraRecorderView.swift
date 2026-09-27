import SwiftUI
import UIKit
import AVFoundation

/// 카메라로 영상을 촬영해 임시 파일 URL 로 돌려주는 뷰 (UIImagePickerController 래핑).
/// 시뮬레이터에는 카메라가 없어 실제 촬영은 실기기에서만 동작한다.
struct CameraRecorderView: UIViewControllerRepresentable {
    /// 촬영 완료 시 녹화된 영상 파일 URL 을 전달 (사용 후 호출한 쪽이 지운다). 취소 시 nil.
    var onFinish: (URL?) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.mediaTypes = ["public.movie"]
        picker.cameraCaptureMode = .video
        picker.videoQuality = .typeHigh
        picker.videoMaximumDuration = VideoCompressor.maxDuration  // 60초가 되면 촬영 자동 종료
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onFinish: onFinish) }

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let onFinish: (URL?) -> Void
        init(onFinish: @escaping (URL?) -> Void) { self.onFinish = onFinish }

        func imagePickerController(_ picker: UIImagePickerController,
                                   didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            // 피커가 준 파일은 닫힌 뒤 지워질 수 있어 임시 폴더로 옮겨 둔다
            var moved: URL?
            if let url = info[.mediaURL] as? URL {
                let dst = FileManager.default.temporaryDirectory
                    .appendingPathComponent(UUID().uuidString)
                    .appendingPathExtension(url.pathExtension)
                if (try? FileManager.default.moveItem(at: url, to: dst)) != nil { moved = dst }
            }
            picker.dismiss(animated: true) { self.onFinish(moved) }
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            picker.dismiss(animated: true) { self.onFinish(nil) }
        }
    }
}

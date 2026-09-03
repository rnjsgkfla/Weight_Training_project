import SwiftUI
import UIKit
import AVFoundation

/// 카메라로 영상을 촬영해 Data 로 돌려주는 뷰 (UIImagePickerController 래핑).
/// 시뮬레이터에는 카메라가 없어 실제 촬영은 실기기에서만 동작한다.
struct CameraRecorderView: UIViewControllerRepresentable {
    /// 촬영 완료 시 녹화된 영상 데이터를 전달. 취소 시 nil.
    var onFinish: (Data?) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.mediaTypes = ["public.movie"]
        picker.cameraCaptureMode = .video
        picker.videoQuality = .typeHigh
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onFinish: onFinish) }

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let onFinish: (Data?) -> Void
        init(onFinish: @escaping (Data?) -> Void) { self.onFinish = onFinish }

        func imagePickerController(_ picker: UIImagePickerController,
                                   didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            var data: Data?
            if let url = info[.mediaURL] as? URL {
                data = try? Data(contentsOf: url)
            }
            picker.dismiss(animated: true) { self.onFinish(data) }
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            picker.dismiss(animated: true) { self.onFinish(nil) }
        }
    }
}

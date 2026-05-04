import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  // Blur overlay shown while the app is in the background / app-switcher.
  // iOS has no equivalent of Android's FLAG_SECURE — we cannot block
  // screenshots — but covering the live window before the system snapshots
  // it for the app-switcher prevents the recents-thumbnail leak path.
  private var privacyOverlay: UIVisualEffectView?

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
  }

  // Add the blur overlay as soon as the app starts resigning active —
  // willResignActive fires BEFORE the system snapshot is taken, so the
  // recents-app card shows the blur, not the story body.
  override func applicationWillResignActive(_ application: UIApplication) {
    super.applicationWillResignActive(application)
    guard let window = self.window else { return }
    if privacyOverlay == nil {
      let blur = UIBlurEffect(style: .systemMaterialDark)
      let overlay = UIVisualEffectView(effect: blur)
      overlay.frame = window.bounds
      overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
      overlay.tag = 9999
      window.addSubview(overlay)
      privacyOverlay = overlay
    }
  }

  // Remove the overlay once we're back in the foreground.
  override func applicationDidBecomeActive(_ application: UIApplication) {
    super.applicationDidBecomeActive(application)
    privacyOverlay?.removeFromSuperview()
    privacyOverlay = nil
  }
}

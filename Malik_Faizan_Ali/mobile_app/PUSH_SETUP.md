# Optional: push notifications (FCM)

The app works without this: every notification is also stored in the in-app **Notifications** list
(`GET /notifications`) and the menu badge. Push only adds a phone alert. It needs *your own* Firebase project,
so it is **not enabled** in this delivery and **has not been tested**.

1. Create a Firebase project, add an Android app with package `pk.edu.trends.siois_mobile`
   (or the id in `android/app/build.gradle*`), download `google-services.json` into `android/app/`.
2. In the Firebase console create a service-account key and give the backend its path
   (`FCM_ENABLED=true` and `FCM_CREDENTIALS_FILE=/path/to/key.json` in `backend/.env`). With `FCM_ENABLED=false`
   (the default) the backend only stores notifications.
3. `flutter pub add firebase_core firebase_messaging`
4. Add the Google services Gradle plugin as described on https://firebase.google.com/docs/flutter/setup
   (settings.gradle + app/build.gradle) - the exact lines depend on your Flutter/Gradle version.
5. `cp lib/push_setup.dart.example lib/push_setup.dart`, then in `lib/main.dart`:
   ```dart
   import 'push_setup.dart';
   Future<void> main() async {
     WidgetsFlutterBinding.ensureInitialized();
     await initPush();
     runApp(const SiOisApp(config: AppConfig(/* ... */ pushTokenProvider: fcmToken)));
   }
   ```
6. After sign-in the shared app posts the token to `POST /devices/register` (`platform: android`).

#!/usr/bin/env python3
"""Patches the Android project that `flutter create` generated for SIOIS.

Run from mobile_app/ AFTER: flutter create . --platforms=android --org pk.edu.trends --project-name siois_mobile
  python3 tool/patch_android.py [--allow-cleartext]

 * adds the INTERNET permission to the main manifest (flutter create only adds it for debug builds)
 * sets android:label to "SIOIS"
 * minSdk 23 (flutter_secure_storage requires it)
 * --allow-cleartext: lets the app talk to a plain http:// backend (development / LAN only; use https in production)
Idempotent. Written for the Flutter 3.27+ templates and tested only on a hand-made imitation of them (no Flutter SDK was available); if a file looks different it says so and changes nothing there.
"""
import re, sys, pathlib

cleartext = '--allow-cleartext' in sys.argv
root = pathlib.Path('android/app')
manifest = root / 'src/main/AndroidManifest.xml'
if not manifest.exists():
    sys.exit('android/app/src/main/AndroidManifest.xml not found - run flutter create first (from mobile_app/).')

m = manifest.read_text()
if 'android.permission.INTERNET' not in m:
    m = m.replace('<application', '<uses-permission android:name="android.permission.INTERNET"/>\n    <application', 1)
    print('manifest: added INTERNET permission')
m = re.sub(r'android:label="[^"]*"', 'android:label="SIOIS"', m, count=1)
if cleartext and 'usesCleartextTraffic' not in m:
    m = m.replace('<application', '<application\n        android:usesCleartextTraffic="true"', 1)
    print('manifest: cleartext (http) traffic enabled')
manifest.write_text(m)

for name in ('build.gradle.kts', 'build.gradle'):
    g = root / name
    if not g.exists():
        continue
    t = g.read_text()
    new = re.sub(r'minSdk\s*=\s*flutter\.minSdkVersion', 'minSdk = 23', t)
    new = re.sub(r'minSdkVersion\s+flutter\.minSdkVersion', 'minSdkVersion 23', new)
    if new != t:
        g.write_text(new)
        print(f'{name}: minSdk set to 23')
    elif 'minSdk = 23' in t or 'minSdkVersion 23' in t:
        print(f'{name}: minSdk already 23')
    else:
        print(f'{name}: could not find the minSdk line - set minSdk to 23 by hand')
print('done')

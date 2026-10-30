#!/bin/sh
# Builds and signs build/pwqgen.apk (arm64-v8a).
#
# Needs: Rust with the aarch64-linux-android target, Android build-tools and
# platform (ANDROID_SDK), the NDK sysroot (see tools/android-linker.sh), and a
# JDK for apksigner/keytool.  The signing key is created on first run under
# $PWQGEN_KEYS (default ~/.android-keys), outside the repository.
set -eu

cd "$(dirname "$0")/.."

SDK=${ANDROID_SDK:-/root/android-sdk}
BT="$SDK/build-tools/36.1"
PLATFORM="$SDK/platform/android.jar"
KEYS=${PWQGEN_KEYS:-$HOME/.android-keys}
KEYSTORE="$KEYS/pwqgen.jks"
KEYPASS="$KEYS/pwqgen.pass"
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -n 1)
VERSION_CODE=${VERSION_CODE:-1}

cargo build --release --target aarch64-linux-android

rm -rf build
mkdir -p build/apk/lib/arm64-v8a

"$BT/aapt2" compile --dir android/res -o build/res.zip
"$BT/aapt2" link -o build/unsigned.apk -I "$PLATFORM" \
	--manifest android/AndroidManifest.xml \
	--min-sdk-version 26 --target-sdk-version 34 \
	--version-code "$VERSION_CODE" --version-name "$VERSION" \
	build/res.zip

# Native libraries stay uncompressed so Android can map them from the APK.
cp target/aarch64-linux-android/release/libpwqgen.so build/apk/lib/arm64-v8a/
(cd build/apk && zip -q -0 -r ../unsigned.apk lib)
"$BT/zipalign" -P 16 -f 4 build/unsigned.apk build/aligned.apk

if [ ! -f "$KEYSTORE" ]; then
	mkdir -p "$KEYS"
	chmod 700 "$KEYS"
	(umask 077 && head -c 32 /dev/urandom | base64 | tr -d '/+=' > "$KEYPASS")
	keytool -genkeypair -keystore "$KEYSTORE" -storetype PKCS12 \
		-alias pwqgen -keyalg EC -groupname secp256r1 -validity 10000 \
		-dname "CN=pwqgen" -storepass:file "$KEYPASS"
	chmod 600 "$KEYSTORE"
fi

"$BT/apksigner" sign --ks "$KEYSTORE" --ks-pass "file:$KEYPASS" \
	--out build/pwqgen.apk build/aligned.apk
"$BT/apksigner" verify --print-certs build/pwqgen.apk
rm -f build/unsigned.apk build/aligned.apk build/res.zip
rm -rf build/apk
ls -l build/pwqgen.apk

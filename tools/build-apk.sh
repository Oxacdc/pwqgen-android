#!/bin/sh
# Builds build/pwqgen.apk for arm64-v8a, armeabi-v7a and x86_64.
#
# Needs Rust with the matching Android targets, an Android SDK with
# build-tools and a platform, an NDK, zip, and a JDK for apksigner/keytool.
#
# Environment:
#   ANDROID_HOME   SDK root (or ANDROID_SDK_ROOT)
#   ANDROID_NDK    NDK root (or ANDROID_NDK_HOME/ANDROID_NDK_ROOT; default:
#                  newest $ANDROID_HOME/ndk/*)
#   BUILD_TOOLS    build-tools version (default: newest installed)
#   ABIS           ABIs to include (default: "arm64-v8a armeabi-v7a x86_64")
#   UNSIGNED=1     stop at build/pwqgen-unsigned.apk (for F-Droid)
#   SCREENSHOTS=1  build without FLAG_SECURE, for store screenshots only
#   PWQGEN_KEYS    signing key directory (default: ~/.android-keys)
set -eu

cd "$(dirname "$0")/.."

newest() {
	ls -1 "$1" | sort -V | tail -n 1
}

SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:?set ANDROID_HOME}}
NDK=${ANDROID_NDK:-${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-$SDK/ndk/$(newest "$SDK/ndk")}}}
BT="$SDK/build-tools/${BUILD_TOOLS:-$(newest "$SDK/build-tools")}"
PLATFORM="$SDK/platforms/$(newest "$SDK/platforms")/android.jar"
ABIS=${ABIS:-arm64-v8a armeabi-v7a x86_64}
KEYS=${PWQGEN_KEYS:-$HOME/.android-keys}
KEYSTORE="$KEYS/pwqgen.jks"
KEYPASS="$KEYS/pwqgen.pass"

manifest_attr() {
	sed -n "s/.*android:$1=\"\([^\"]*\)\".*/\1/p" android/AndroidManifest.xml | head -n 1
}

MIN_SDK=$(manifest_attr minSdkVersion)
VERSION_NAME=$(manifest_attr versionName)
CARGO_VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -n 1)
if [ "$VERSION_NAME" != "$CARGO_VERSION" ]; then
	echo "versionName $VERSION_NAME (AndroidManifest.xml) != version $CARGO_VERSION (Cargo.toml)" >&2
	exit 1
fi

FEATURES=
OUTPUT=pwqgen
if [ "${SCREENSHOTS:-0}" = 1 ]; then
	FEATURES="--features screenshots"
	OUTPUT=pwqgen-screenshots
fi

rm -rf build
mkdir -p build/apk

export ANDROID_NDK="$NDK"
for abi in $ABIS; do
	case $abi in
	arm64-v8a) rust=aarch64-linux-android clang=aarch64-linux-android ;;
	armeabi-v7a) rust=armv7-linux-androideabi clang=armv7a-linux-androideabi ;;
	x86_64) rust=x86_64-linux-android clang=x86_64-linux-android ;;
	*) echo "unknown ABI: $abi" >&2; exit 1 ;;
	esac
	linker_var=CARGO_TARGET_$(echo "$rust" | tr 'a-z-' 'A-Z_')_LINKER
	env "$linker_var=$PWD/tools/android-linker.sh" \
		ANDROID_CLANG_TARGET="$clang$MIN_SDK" \
		cargo build --locked --release --target "$rust" $FEATURES
	mkdir -p "build/apk/lib/$abi"
	cp "target/$rust/release/libpwqgen.so" "build/apk/lib/$abi/"
done

"$BT/aapt2" compile --dir android/res -o build/res.zip
"$BT/aapt2" link -o build/base.apk -I "$PLATFORM" \
	--manifest android/AndroidManifest.xml build/res.zip

# Native libraries stay uncompressed so Android can map them from the APK.
(cd build/apk && zip -q -0 -r ../base.apk lib)
"$BT/zipalign" -P 16 -f 4 build/base.apk "build/$OUTPUT-unsigned.apk"
rm -rf build/apk build/base.apk build/res.zip

if [ "${UNSIGNED:-0}" = 1 ]; then
	ls -l "build/$OUTPUT-unsigned.apk"
	exit 0
fi

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
	--out "build/$OUTPUT.apk" "build/$OUTPUT-unsigned.apk"
"$BT/apksigner" verify --print-certs "build/$OUTPUT.apk"
rm -f "build/$OUTPUT-unsigned.apk" "build/$OUTPUT.apk.idsig"
ls -l "build/$OUTPUT.apk"

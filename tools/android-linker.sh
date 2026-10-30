#!/bin/sh
# Cargo linker for Android targets, set up by tools/build-apk.sh.
#
# ANDROID_NDK: NDK root.  ANDROID_CLANG_TARGET: clang target with API level,
# e.g. aarch64-linux-android26.
set -eu

LLVM="$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64"

if "$LLVM/bin/clang" --version >/dev/null 2>&1; then
	exec "$LLVM/bin/clang" --target="$ANDROID_CLANG_TARGET" "$@"
fi

# Hosts where the NDK's glibc binaries don't run (e.g. Alpine): use the system
# clang and lld with the NDK's sysroot and runtime libraries.
exec clang --target="$ANDROID_CLANG_TARGET" --sysroot="$LLVM/sysroot" \
	-resource-dir="$(echo "$LLVM"/lib/clang/*)" -rtlib=compiler-rt \
	-fuse-ld=lld "$@"

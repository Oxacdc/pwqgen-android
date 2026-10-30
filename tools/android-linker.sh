#!/bin/sh
# Links aarch64 Android binaries with the host clang/lld and the NDK sysroot.
NDK=${ANDROID_NDK_TOOLCHAIN:-/root/android-sdk/ndk/toolchains/llvm/prebuilt/linux-x86_64}
exec clang --target=aarch64-linux-android26 --sysroot="$NDK/sysroot" \
	-resource-dir="$(echo "$NDK"/lib/clang/*)" -rtlib=compiler-rt \
	-fuse-ld=lld "$@"

#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
android_dir="$project_dir/android"
source_apk="$android_dir/app/build/outputs/apk/debug/app-debug.apk"
release_apk="$project_dir/releases/JARVIS.apk"

if [[ -z "${ANDROID_HOME:-}" && -d "$HOME/Library/Android/sdk" ]]; then
  export ANDROID_HOME="$HOME/Library/Android/sdk"
fi

if [[ -z "${ANDROID_HOME:-}" ]]; then
  echo "ANDROID_HOME을 Android SDK 경로로 설정해 주세요." >&2
  exit 1
fi

cd "$android_dir"
./gradlew assembleDebug
mkdir -p "$project_dir/releases"
cp "$source_apk" "$release_apk"
echo "배포 APK 준비 완료: $release_apk"

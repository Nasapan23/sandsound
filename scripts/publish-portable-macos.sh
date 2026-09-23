#!/usr/bin/env bash
set -euo pipefail

architecture=""
skip_tool_download=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --architecture)
      architecture="${2:-}"
      shift 2
      ;;
    --skip-tool-download)
      skip_tool_download=true
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "The macOS portable bundle must be assembled on macOS." >&2
  exit 1
fi

if [[ -z "$architecture" ]]; then
  case "$(uname -m)" in
    arm64) architecture="arm64" ;;
    x86_64) architecture="x64" ;;
    *) echo "Unsupported macOS architecture: $(uname -m)" >&2; exit 1 ;;
  esac
fi

case "$architecture" in
  arm64) ffmpeg_arch="arm64" ;;
  x64) ffmpeg_arch="x64" ;;
  *) echo "Architecture must be 'arm64' or 'x64'." >&2; exit 2 ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
project="$repo_root/native/SandSound.Mac/SandSound.Mac.csproj"
output="$repo_root/artifacts/SandSound-macos-$architecture"
app_bundle="$output/SandSound.app"
macos_dir="$app_bundle/Contents/MacOS"
cache="$repo_root/artifacts/.cache/macos-$architecture"
tools="$macos_dir/Tools"

case "$output" in
  "$repo_root"/artifacts/SandSound-macos-*) ;;
  *) echo "Refusing to replace an output directory outside this repository." >&2; exit 1 ;;
esac

rm -rf "$output"
mkdir -p "$macos_dir" "$app_bundle/Contents/Resources" "$tools" "$output/Data" "$output/Downloads" "$cache"

dotnet_command="dotnet"
if [[ -x "$repo_root/.tools/dotnet/dotnet" ]]; then
  dotnet_command="$repo_root/.tools/dotnet/dotnet"
fi

"$dotnet_command" publish "$project" \
  --configuration Release \
  --runtime "osx-$architecture" \
  --self-contained true \
  --output "$macos_dir" \
  -p:PublishSingleFile=true \
  -p:IncludeNativeLibrariesForSelfExtract=true

cp "$repo_root/native/SandSound.Mac/Info.plist" "$app_bundle/Contents/Info.plist"
chmod +x "$macos_dir/SandSound"

if [[ "$skip_tool_download" == false ]]; then
  yt_dlp="$cache/yt-dlp"
  if [[ ! -f "$yt_dlp" ]]; then
    curl --fail --location --retry 3 \
      "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos" \
      --output "$yt_dlp"
  fi

  ffmpeg="$cache/ffmpeg"
  ffprobe="$cache/ffprobe"
  ffmpeg_release="b6.1.1"
  if [[ ! -f "$ffmpeg" ]]; then
    curl --fail --location --retry 3 \
      "https://github.com/eugeneware/ffmpeg-static/releases/download/$ffmpeg_release/ffmpeg-darwin-$ffmpeg_arch" \
      --output "$ffmpeg"
  fi
  if [[ ! -f "$ffprobe" ]]; then
    curl --fail --location --retry 3 \
      "https://github.com/eugeneware/ffmpeg-static/releases/download/$ffmpeg_release/ffprobe-darwin-$ffmpeg_arch" \
      --output "$ffprobe"
  fi

  cp "$yt_dlp" "$tools/yt-dlp"
  cp "$ffmpeg" "$tools/ffmpeg"
  cp "$ffprobe" "$tools/ffprobe"
  chmod +x "$tools/yt-dlp" "$tools/ffmpeg" "$tools/ffprobe"
fi

# Ad-hoc signing keeps the bundle internally consistent for local and CI builds.
# Set APPLE_CODESIGN_IDENTITY to use a Developer ID certificate before notarizing.
signing_identity="${APPLE_CODESIGN_IDENTITY:--}"
codesign --force --deep --sign "$signing_identity" "$app_bundle"

size="$(du -sh "$output" | awk '{print $1}')"
echo "Portable SandSound created at: $output"
echo "Total size: $size"
echo "Copy the complete folder and open SandSound.app."

#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: make_contact_sheet.sh <output.jpg> <image> [image...]

Creates one small 4-column JPEG contact sheet. Use only this sheet for review;
do not open the original full-resolution images in the main chat.
EOF
  exit 2
}

[[ $# -ge 2 ]] || usage

output="$1"
shift
[[ -d "$(dirname "$output")" ]] || mkdir -p "$(dirname "$output")"

script_dir="$(cd "$(dirname "$0")" && pwd)"
python3 "$script_dir/session_budget.py" --strict >&2

ffmpeg_bin="$HOME/workspace/ffmpeg-full/ffmpeg"
[[ -x "$ffmpeg_bin" ]] || ffmpeg_bin="$(command -v ffmpeg || true)"
[[ -n "$ffmpeg_bin" ]] || {
  echo "ffmpeg not found" >&2
  exit 1
}
ffprobe_bin="${ffmpeg_bin%ffmpeg}ffprobe"
[[ -x "$ffprobe_bin" ]] || ffprobe_bin="$(command -v ffprobe || true)"
[[ -n "$ffprobe_bin" ]] || {
  echo "ffprobe not found" >&2
  exit 1
}

tmp_dir="$(mktemp -d /tmp/xiyou-contact.XXXXXX)"
trap 'find "$tmp_dir" -type f -delete 2>/dev/null || true; rmdir "$tmp_dir" 2>/dev/null || true' EXIT

count=0
for source in "$@"; do
  [[ -f "$source" ]] || {
    echo "missing image: $source" >&2
    exit 1
  }
  count=$((count + 1))
  index="$(printf '%02d' "$count")"
  label="$(printf '%02d' "$count")"
  "$ffmpeg_bin" -hide_banner -loglevel error -nostdin -y -i "$source" \
    -vf "scale=320:180:force_original_aspect_ratio=decrease:flags=lanczos,pad=320:180:(ow-iw)/2:(oh-ih)/2:color=0x202020,drawtext=fontfile=/System/Library/Fonts/Hiragino Sans GB.ttc:text='$label':x=8:y=h-24:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.65" \
    -frames:v 1 -q:v 5 "$tmp_dir/$index.jpg"
done

rows=$(( (count + 3) / 4 ))
"$ffmpeg_bin" -hide_banner -loglevel error -nostdin -y -framerate 1 \
  -pattern_type glob -i "$tmp_dir/*.jpg" \
  -vf "tile=4x${rows}:padding=4:margin=4:color=0x202020" \
  -frames:v 1 -q:v 6 "$output"

size_bytes="$(wc -c < "$output" | tr -d ' ')"
if (( size_bytes > 1048576 )); then
  compact="${output%.jpg}.compact.jpg"
  "$ffmpeg_bin" -hide_banner -loglevel error -nostdin -y -i "$output" \
    -vf "scale=960:-2:flags=lanczos" -q:v 8 "$compact"
  mv "$compact" "$output"
  size_bytes="$(wc -c < "$output" | tr -d ' ')"
fi

width_height="$("$ffprobe_bin" -v error -select_streams v:0 \
  -show_entries stream=width,height -of csv=s=x:p=0 "$output")"
printf 'contact_sheet=%s\nsize_bytes=%s\ndimensions=%s\nimages=%s\n' \
  "$output" "$size_bytes" "$width_height" "$count"
printf '%s\n' 'safe_to_view=yes_one_sheet_only'

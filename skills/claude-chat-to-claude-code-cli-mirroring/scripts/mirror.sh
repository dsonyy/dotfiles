#!/usr/bin/env bash
set -euo pipefail

limit=${1:-10}
[[ $limit =~ ^[1-9][0-9]*$ ]] || { echo "Usage: mirror.sh [conversation_count]" >&2; exit 1; }

key_file=~/sessionKey
cwd=$HOME/brain
project_dir=~/.claude/projects/$(sed 's#[/.]#-#g' <<<"$cwd")
cookie_hint="Copy the sessionKey cookie value from claude.ai (F12 > Application > Cookies > https://claude.ai) into $key_file"

[[ -s $key_file ]] || { echo "Missing cookie. $cookie_hint" >&2; exit 1; }
key=$(tr -d '[:space:]' <"$key_file")

api() {
  local out code body
  out=$(curl -sS -w $'\n%{http_code}' \
    -H "Cookie: sessionKey=$key" \
    -H 'Accept: */*' \
    -H 'anthropic-client-platform: web_claude_ai' \
    -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36' \
    "https://claude.ai/api/$1")
  code=${out##*$'\n'}
  body=${out%$'\n'*}
  if [[ $code == 200 ]]; then
    printf '%s' "$body"
  elif [[ $code =~ ^40[13]$ && $body == \{* ]]; then
    echo "Cookie invalid or expired. $cookie_hint" >&2
    return 1
  else
    echo "HTTP $code error for /api/$1: ${body:0:200}" >&2
    return 1
  fi
}

orgs=$(api organizations)
org=$(jq -r '(map(select(.capabilities // [] | index("chat"))) + .)[0].uuid // empty' <<<"$orgs")
[[ -n $org ]] || { echo "No organization found on this account." >&2; exit 1; }

convs=$(api "organizations/$org/chat_conversations?limit=$limit")
ids=$(jq -r --argjson n "$limit" 'sort_by(.updated_at) | reverse | .[:$n][] | .uuid' <<<"$convs")

mkdir -p "$project_dir"
written=0 skipped=0 empty=0

for id in $ids; do
  file=$project_dir/$id.jsonl
  if [[ -f $file && $(wc -l <"$file") -ne 3 ]]; then
    skipped=$((skipped + 1))
    continue
  fi

  conv=$(api "organizations/$org/chat_conversations/$id?tree=True&rendering_mode=messages")

  lines=$(jq -c --arg cwd "$cwd" --arg u1 "$(uuidgen)" --arg u2 "$(uuidgen)" '
    def block:
      if .type == "text" then .text
      elif .type == "tool_use" then "[tool: \(.name)] \(.input | tojson)"
      else empty end;
    def render:
      "## " + (if .sender == "human" then "User" else "Claude" end) + "\n\n" +
      ([ (if (.content // []) | length > 0 then .content[] | block else .text // empty end),
         (.attachments[]? | "[attachment: \(.file_name)]\n\(.extracted_content // "")"),
         (.files[]? | "[file: \(.file_name // .file_uuid)]") ] | join("\n\n"));
    (.chat_messages | map({key: .uuid, value: .}) | from_entries) as $m
    | (if $m[.current_leaf_message_uuid // ""] then
         [ .current_leaf_message_uuid | recurse($m[.].parent_message_uuid; $m[.] != null) | $m[.] ] | reverse
       else .chat_messages end) as $msgs
    | select($msgs | length > 0)
    | (.name // "" | if . == "" then "Untitled" else . end) as $title
    | ("# \($title)\n\nTranscript of a claude.ai conversation (\(.uuid)), imported as context.\n\n" + ($msgs | map(render) | join("\n\n"))) as $md
    | {type: "user", parentUuid: null, isSidechain: false, uuid: $u1, sessionId: .uuid, cwd: $cwd,
       timestamp: .created_at, userType: "external", message: {role: "user", content: $md}},
      {type: "assistant", parentUuid: $u1, isSidechain: false, uuid: $u2, sessionId: .uuid, cwd: $cwd,
       timestamp: .updated_at, userType: "external",
       message: {role: "assistant", type: "message", model: (.model // "claude"), content: [{type: "text", text: "OK"}]}},
      {type: "ai-title", aiTitle: "[MIRROR] \($title)", sessionId: .uuid}
  ' <<<"$conv")

  if [[ -z $lines ]]; then
    empty=$((empty + 1))
    continue
  fi

  printf '%s\n' "$lines" >"$file"
  touch -d "$(jq -r .updated_at <<<"$conv")" "$file"
  written=$((written + 1))
  titles+=("- $(tail -n1 <<<"$lines" | jq -r .aiTitle)")
done

echo "Written: $written, skipped (modified locally): $skipped, empty: $empty. Directory: $project_dir"
((written)) && printf '%s\n' "${titles[@]}"
exit 0

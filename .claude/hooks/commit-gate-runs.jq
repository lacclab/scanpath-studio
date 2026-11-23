# The programs a session's shell commands ran, one per line, for the commit
# gate's `ran=` field. Read with `jq -r -f` over the session's transcripts.
#
# Text in a command is not a run: heredoc bodies and quoted strings (a commit
# message, a PR body, a grep pattern) are removed first. The command is then
# split into the programs it chains, and each program loses its environment
# assignments, its `time` / `timeout` / `xargs` wrapper, `uv run` and its
# options, and the Python interpreter and its options. What is left starts
# with the program that ran: `pytest …` or `scripts/verify_change.py …`.
select(.type == "assistant")
| .message.content[]?
| select(.type == "tool_use" and .name == "Bash")
| .input.command // empty
| gsub("<<-?\\s*[\"']?(?<tag>\\w+)[\"']?[^\\n]*\\n[\\s\\S]*?\\n\\s*\\k<tag>(?=\\n|$)"; "")
| gsub("\\\\\\n"; " ")
| gsub("'[^']*'"; "")
| gsub("\"([^\"\\\\]|\\\\.)*\""; "")
| splits("[;&|()\\n]+")
| sub("^\\s+"; "")
| sub("^((\\w+=\\S*|env|nice|xargs|(\\S*/)?time|-p|timeout\\s+\\S+)\\s+)*"; "")
| sub("^uv\\s+((--(directory|project|python|config-file|cache-dir)\\s+\\S+|--?[\\w-]+(=\\S+)?)\\s+)*run\\s+((--(extra|with|python|group|package|directory|project|env-file|index)\\s+\\S+|--?[\\w-]+(=\\S+)?)\\s+)*"; "")
| sub("^(\\S*/)?python[\\d.]*\\s+((-[IuBOEsS]+|-[XW]\\s+\\S+|-m)\\s+)*"; "")

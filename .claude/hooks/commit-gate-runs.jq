# The programs a session's shell commands ran, one per line, for the commit
# gate's `ran=` field. Read with `jq -R -r -f` over the session's transcripts,
# so a line cut short while the transcript is written skips only itself.
#
# Text in a command is not a run: heredoc bodies and quoted strings (a commit
# message, a PR body, a grep pattern) are removed first, quotes matched left to
# right so an apostrophe inside double quotes stays inside them. The command
# is then split into the programs it chains, and each program loses the shell
# keywords and wrappers in front of it (`do`, `if`, `!`, `{`, `exec`, `env`,
# `nice`, `time`, `timeout`, `xargs`, environment assignments), `uv run` and
# its options, and the Python interpreter and its options. What is left starts
# with the program that ran: `pytest …` or `scripts/verify_change.py …`.
fromjson? // empty
| select(.type == "assistant")
| .message.content[]?
| select(.type == "tool_use" and .name == "Bash")
| .input.command // empty
| gsub("<<-?\\s*[\"']?(?<tag>(?>\\w+))[\"']?[^\\n]*\\n[\\s\\S]*?\\n\\s*\\k<tag>(?=\\n|$)"; "")
| gsub("\\\\\\n"; " ")
| gsub("'[^']*'|\"([^\"\\\\]|\\\\.)*\""; "")
| splits("[;&|()\\n]+")
| sub("^\\s+"; "")
| sub("^((do|then|else|elif|if|while|until|!|\\{|exec|command|\\w+=\\S*|env(\\s+-u\\s+\\S+|\\s+-\\S+)*|nice(\\s+-n\\s+\\S+|\\s+-\\S+)*|xargs(\\s+-\\S+)*|(\\S*/)?time|-p|timeout\\s+\\S+)\\s+)*"; "")
| sub("^uv\\s+((--(directory|project|python|config-file|cache-dir)\\s+\\S+|--?[\\w-]+(=\\S+)?)\\s+)*run\\s+((--(extra|with|python|group|package|directory|project|env-file|index)\\s+\\S+|-p\\s+\\S+|--?[\\w-]+(=\\S+)?)\\s+)*"; "")
| sub("^(\\S*/)?python[\\d.]*\\s+((-[IuBOEsS]+|-[XW]\\s+\\S+|-m)\\s+)*"; "")

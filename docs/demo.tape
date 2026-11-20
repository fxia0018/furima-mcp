# Records docs/demo.gif with https://github.com/charmbracelet/vhs
# Run from the repo root: vhs docs/demo.tape

Output docs/demo.gif
Require claude
Require uvx

Set Shell zsh
Set FontSize 16
Set Width 1280
Set Height 960
Set Padding 16
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set BorderRadius 10
Set Margin 24
Set MarginFill "#1e1e2e"
Set TypingSpeed 45ms

Hide
Type `mkdir -p /tmp/furima-demo && cd /tmp/furima-demo && clear && claude --strict-mcp-config --mcp-config '{"mcpServers":{"furima":{"command":"uvx","args":["furima-mcp"]}}}' --allowedTools 'mcp__furima__*' --permission-mode default` Enter
Sleep 5s
# First run in a new folder asks whether to trust it
Down
Enter
Sleep 6s
Show

Type "Is ¥30,000 a good price for a used Switch OLED?"
Sleep 600ms
Enter
Wait+Screen@90s /· done /
Sleep 6s

Hide
Ctrl+C
Ctrl+C

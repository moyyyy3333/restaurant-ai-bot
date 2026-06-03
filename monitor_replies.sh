# Restaurant Bot - SMS Reply Monitor
# Checks for incoming iMessage replies every 15 minutes
# If a reply is detected, it will be logged here

MONITOR_DB="/tmp/_sms_monitor.json"

# Try to read Messages chat DB (will fail until Full Disk Access is granted)
# But when it works, it automatically alerts

if [ -r ~/Library/Messages/chat.db ]; then
    echo "Chat DB readable! Checking for replies..."
    sqlite3 ~/Library/Messages/chat.db "
    SELECT datetime(m.date/1000000000 + 978307200, 'unixepoch'), h.id, m.text
    FROM message m
    JOIN handle h ON h.ROWID = m.handle_id
    WHERE m.is_from_me = 0
      AND m.text IS NOT NULL
      AND m.date > (strftime('%s','now','-24 hours') - 978307200) * 1000000000
    ORDER BY m.date DESC;
    " 2>/dev/null
else
    echo "Monitor standing by - DB locked (need Full Disk Access)"
    echo "No replies detected since script can't read Messages."
fi

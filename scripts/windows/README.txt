Marcarr for Windows (portable)
==============================

1. Unzip this folder anywhere you can write to (not Program Files).
2. Double-click Marcarr.bat. Your browser opens http://127.0.0.1:7470; the first run walks you through
   connecting Plex.
3. Close the window to stop it.

Your settings and data are in the "config" folder here. To update, unzip the new version over a new
folder and copy "config" across.

Other commands, from a Command Prompt in this folder:
  Marcarr.bat scan              read Plex once
  Marcarr.bat analyse file.mkv  analyse one file, no Plex needed
  Marcarr.bat status            the queue and the month's AI cost

The "python" folder is an embedded Python with Marcarr installed; "ffmpeg" holds ffmpeg and ffprobe
(a GPL build from https://github.com/BtbN/FFmpeg-Builds, its license is in ffmpeg\LICENSE.txt).

https://github.com/jhd3197/Marcarr

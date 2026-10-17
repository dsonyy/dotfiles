---
name: music-integrating
description: Use this skill every time you do anything with music, the music library, playlists or Navidrome.
---

Library is `~/data/music`, served by Navidrome. Config in `~/repos/dotfiles/services/navidrome/`. Navidrome picks up file changes on its own.

- Layout: `<Album Artist> - <Album>/NN - <Title>.<ext>`
- Tracks without an album: `<Album Artist> - Singles/`, album `Singles`
- Compilations: `Various Artists - <Album>/`, compilation flag set
- Required tags: title, artist, album, album artist, track number
- Cover: `cover.jpg` in the album folder and embedded
- Source URL in the comment tag
- Playlists: `.m3u` in `playlists/`, paths relative. Files are the source of truth, not the app.

# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- `queue` subcommands added to modify the current songs in the queue
    - `add` to add a song to the queue. Alternate method of using `play` when a song is already playing
    - `remove` to remove a song from the queue
    - `list` to list all songs in the queue. Executed by `queue` command if no subcommand is given
    - `move` to move a selected song in the queue to a different position
    - `clear` to remove all songs in the queue
- `playlist` command holds all the subcommands for playlist related tools
    - `play` command play a selected playlist, playing the first song if no song is currently playing and adding the rest to the queue
    - `create` to create a new playlist
    - `destroy` to remove an existing playlist
    - `rename` to rename an existing playlist
    - `description` to set a playlist description
    - `list` to view all playlists
    - `add` to add a new song to an existing playlist
    - `remove` to remove a song from a playlist
    - `move` to move a selected song in a playlist to a different position
    - `view` to view the songs in the selected playlist
- `shuffle` command to move the songs in the current queue to random positions
- Spoiler tag applied to gifs that were converted from WebPs
- Launch arguments for admin user and command prefix
- Argument passing through run scripts
- Error output when trying to play an unavailable youtube video

### Changed
- Moved data, logs, cache, and assets to their own separate directories outside of the source folder
- Arguments are now parsed before config creation, which can be used to skip the introduction altogether
- Change database table and key naming convention
- Adminuser config entry list based with integer entries to support multiple bot admins
- Introduction text reworded
- Song queue limit increased to 100

### Fixed
- Including directory with the file path rather than changing paths. This solves many IO requests when IO commands are executed quickly in succession

## [0.2.1] - 2020-01-30
### Fixed
- Song time in queue still counting up when song is paused
- YouTube-DL failing to fetch some videos (Version bumped all requirements)

## [0.2.0] - 2019-12-21
### Added
- Repeat message using echo
- Bot wide custom prefix using globalprefix
- Server wide custom prefix using prefix
- Reset prefix to global prefix using resetprefix
- Bot commands now callable using bot mention
- Fetch top 5 YouTube results using playsearch for use in music playback
- Set server wide dynamic command aliases using alias
- Script based setup to handle running the program inside of a virtual environment
- Setup.py for distribution purposes
- Makefile for easy development environment setup

### Changed
- First run setup to be more streamlined including prefix setting
- README to include new instructions and requirements utilising the script based setup and start

### Fixed
- Automatic WebP conversion trying to convert static images
- Setup process failing if bot is exited during setup

## [0.1.3] - 2019-12-06
### Fixed
- Invalid config check preventing a fresh install of the bot to run

## [0.1.2] - 2019-10-30
### Fixed
- Looped songs volume doubling and being invalidated due to incorrect FFmpeg calls
- Current duration in looped songs
- Enable command not handling already enabled modules
- Startup modules function trying to remove disabled modules twice (may have fixed enabling disabled modules)

## [0.1.1] - 2019-10-24
### Changed
- Music player now streams rather than downloading music before playing
- Queue now shows additional time information such as song duration, current time in song, and total queue time
- Queue shows how many songs there are past 10 songs
- Song limit set to 3 hours

### Fixed
- Proper conversion error message
- Directory not changing properly when spamming webps
- Gifs not being removed properly when message sending fails
- Text message being removed on image conversion
- Queue not showing when too many songs are added by setting a limit
- Queue now works across multiple servers without conflicting

## [0.1.0] - 2019-10-19
### Added
- First pre-release version 🎉
- Discord.py API to create a modular Python bot system
- Simple user editable TOML based config
- SQLite database for persistent data storage
- **SpaceCat** module for basic bot tools (disable, enable, exit, modules, ping, reload, version)
- **Alexa** module for music playback (join, leave, loop, pause, play, queue, resume, skip, stop)
- **Configuration** module for configuring the bot (activity, perm, permpreset, status)
- **PoliteCat** module for image based functions (react, reactcfg, reactlist)
- **Seethreepio** module for fun text based functions (flip, stealuserpic, throw)

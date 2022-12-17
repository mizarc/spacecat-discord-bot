# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 18-12-2022
### Added
- Support for slash commands, as per the new discord command system guidelines.
- `Automation` module introduced, allowing you to create scheduled events to perform certain actions.
  - User friendly `remindme` command, allowing users to be messaged back with a set message after a set time period.
  - `reminder` allows users to view and delete existing reminders set by the user running the command.
    - `list` subcommand lists all set reminders.
    - `remove` subcommand removes a set reminder.
  - `event` command tree to be used to schedule events for server administrators.
    - `list` subcommand displays all set events.
    - `create` subcommand creates a new event, complete with a name, execution time, and repeat interval.
    - `destroy` subcommand removes an existing event.
    - `view` subcommand displays set actions and time values of a defined event.
    - `add` subcommand allows for the addition of actions that the event is to execute on execution time. Valid actions are listed below.
    - `remove` subcommand removes one of the set actions that an event is to execute.
    - `reorder` subcommand moves the execution position of an event action.
    - `pause` subcommand stops the event from executing at the set time.
    - `resume` subcommand undoes the paused state of the event, allowing it to run at the set time.
    - `rename` subcommand allows you to change the name of a set event.
    - `description` subcommand changes the description of the event.
    - `reschedule` subcommand changes the execution time of the event.
    - `interval` changes the repeat interval of the event.
  - `timezone` command allows you to specify what timezone the server resides in for scheduling purposes.
- Available event actions:
  - `message` outputs a specified message.
  - `broadcast` outputs an embed with a header and message.
  - `voicekick` removes all users from a voice channel.
  - `voicemove` moves all users from a voice channel to another voice channel.
  - `channelprivate` sets a channel to private for @everyone.
  - `channelpublic` set a channel to public for @everyone.
- Spotify support for music playback. Input any spotify song/album/playlist link and it'll play and fetch the correct metadata.
- YouTube playlist support for music playback.
- YouTube Music album support for music playback.

### Changed
- `queue add` subcommand now takes in a position argument. Songs can be added to a specific index of the queue.
- Music player now uses Lavalink backend. This should make songs faster to load and use less memory.
- Song queries now default to use YouTube music for song searching.
- Music module renamed from `Alexa` to `MusicBox`
- `loop` command now doesn't unloop. Separate `unloop` command is now used for undoing song loops.
- `playlist move` subcommand renamed to `playlist reorder`.
- Duration limit lifted for music playback.
- Queue now has clickable links.
- Queue now shows only 5 songs. More would be preferrable but clickable links make it very easy to go over embed character limit.
- Playlists now show creation and modification date. Existing playlists will not have this information.

### Removed
- Custom command prefixes begone with the removal of the `alias` comamnd group. Discord now enforces that all commands should be run through slash commands, and so custom definable prefixes are now erased.
- Command permissions are no longer necessary since the introduction of Discord's own command permission system.
- Linking hidden text channels to voice channels no longer necessary since Discord introduced voice text channels (Seems to be a pattern here for removals huh.)

### Fixed
- Music player auto disconnection not occurring after 5 minutes.
- Certain songs not playing due to FFmpeg incompatibilities.

### Optimised
- Songs should start playing much faster.
- `playsearch` should now work much faster to return song results.
- Playlist links should be parsed much faster.

## [0.4.0] - 26-06-2020
### Added
- Instance menu display on startup to run and edit available instances
    - `NEW INSTANCE`: Creates a new folder in the data folder as an instance
    - `RENAME INSTANCE`: Renames an existing instances
    - `DELETE INSTANCE`: Deletes an existing instance and removes all of its data
    - `EXIT`: Closes the program
- `permpreset` command group to manage global permissions
    - `create` to create a new permission preset
    - `destroy` to remove an existing preset
    - `add` to add a valid permission to a preset
    - `destroy` to remove a permission from a preset
    - `list` to output a list of all available presets
    - `view` to show what permissions a preset contains
- Various new subcommands added to `perm`
    - `presets` to allow server admins to list and view presets set by the bot admin
    - `group preset` to assign a preset to a group
    - `group unpreset` to remove a preset from a group
- Add module to handle the automatic showing and hiding of text channels on voice connects and disconnects
    - `linkchannels` to link a voice and text channel
    - `unlinkchannels` to unlink a voice and text channel
    - `listlinkchannels` to list the currently linked text and voice channels
- Permissions in the default preset are assigned to every user
- Presets assigned to a group read permissions from the config on command checks
- Extended descriptions to the `SpaceCat` module commands
- Constants helper to hold all old and new constant variables
- Auto voice channel disconnection when no users are in the voice channel
- Auto voice channel disconnection when nothing has been playing for a specified amount of time
- New section to the config pertaining to holding variables of music features
- Flake8 linter now used to better confirm to PEP8

### Changed
- Revamp the `help` menu to use embeds for pretty formatting
- `help` command without arguments now only shows modules to reduce clutter
- Disallow users to view module and command `help` pages they don't have permission for
- `playlist` command now defaults to `playlist list` subcommand
- Negative successful embed results to use an orange colour to better distinguish embed results
- Large embeds now use emojis instead of image icons
- Embed number buttons to dynamically convert numbers to emojis and vice versa

### Fixed
- New servers not being added to the database
- Playsearch result fetching due to change on youtube's end

## [0.3.1] - 2020-02-23
### Fixed
- Unable to enable or disable modules
- Module list failing to output after a module has been disabled and re-enabled

## [0.3.0] - 2020-02-08
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
- Top level run.py file for debugging
- Error output when trying to play an unavailable youtube video
- Error output for missing arguments
- Error output for bot missing permissions

### Changed
- Song queue limit increased to 100
- Arguments are now parsed before config creation, which can be used to skip the introduction altogether
- Adminuser config entry list based with integer entries to support multiple bot admins
- Moved data, logs, cache, and assets to their own separate directories outside of the source folder
- Introduction text reworded
- Change database table and key naming convention
- Package renamed to spacecat in setup.py
- Bot is now officially run using python's -m argument

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

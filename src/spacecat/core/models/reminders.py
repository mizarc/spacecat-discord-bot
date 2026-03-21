class Reminder:
    """
    Represents a reminder that a user can set.

    Users use reminders to remind them of something at a set
    time. This class encapsulates all the data required to perform a
    reminder call, including the time and message to send.
    """

    def __init__(
        self: Reminder,
        id_: uuid.UUID,
        user_id: int,
        guild_id: int,
        channel_id: int,
        message_id: int,
        creation_time: int,
        dispatch_time: int,
        message: str,
    ) -> None:
        """
        Initialises a new instance of the Reminder class.

        Args:
            self: The Reminder instance being initialised.
            id_: The unique identifier for the reminder.
            user_id: The ID of the user associated with the
                reminder.
            guild_id: The ID of the guild associated with the
                reminder.
            channel_id: The ID of the channel where the reminder
                was created.
            message_id: The ID of the message that triggered the
                reminder.
            creation_time: The timestamp when the reminder was
                created.
            dispatch_time: The timestamp when the reminder should
                be dispatched.
            message: The message content of the reminder.

        Returns:
            None
        """
        self.id: uuid.UUID = id_
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.creation_time = creation_time
        self.dispatch_time = dispatch_time
        self.message = message

    @classmethod
    def create_new(
        cls: type[Reminder],
        user_id: int,
        guild_id: int,
        channel_id: int,
        message_id: int,
        creation_time: int,
        dispatch_time: int,
        message: str,
    ) -> Reminder:
        """
        Creates a new instance of the Reminder class.

        Args:
            cls: The class object.
            user_id: The ID of the associated user.
            guild_id: The ID of the associated guild.
            channel_id: The ID of the channel where the
                reminder was created.
            message_id: The ID of the message that triggered the
                reminder.
            creation_time: The timestamp when the reminder was
                created.
            dispatch_time: The timestamp when the reminder should
                be dispatched.
            message: The message content of the reminder.

        Returns:
            Reminder: The newly created Reminder instance.
        """
        return cls(
            uuid.uuid4(),
            user_id,
            guild_id,
            channel_id,
            message_id,
            creation_time,
            dispatch_time,
            message,
        )


class ReminderRepository:
    """
    Repository for managing Reminder data storage.

    This class handles the database operations for Reminder instances,
    including creation, retrieval, update, and deletion.
    """

    def __init__(self: ReminderRepository, database: sqlite3.Connection) -> None:
        """
        Initialises a new ReminderRepository instance.

        Args:
            database (sqlite3.Connection): The database connection.
        """
        self.database = database
        self._create_table()

    def _create_table(self: ReminderRepository) -> None:
        """Creates the reminders table if it doesn't exist."""
        cursor = self.database.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                creation_time INTEGER NOT NULL,
                dispatch_time INTEGER NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        self.database.commit()

    def add(self: ReminderRepository, reminder: Reminder) -> None:
        """
        Adds a reminder to the repository.

        Args:
            reminder (Reminder): The reminder to add.
        """
        cursor = self.database.cursor()
        cursor.execute(
            """
            INSERT INTO reminders (
                id, user_id, guild_id, channel_id, message_id,
                creation_time, dispatch_time, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(reminder.id),
                reminder.user_id,
                reminder.guild_id,
                reminder.channel_id,
                reminder.message_id,
                reminder.creation_time,
                reminder.dispatch_time,
                reminder.message,
            ),
        )
        self.database.commit()

    def get_by_id(self: ReminderRepository, reminder_id: uuid.UUID) -> Reminder | None:
        """
        Retrieves a reminder by its ID.

        Args:
            reminder_id (uuid.UUID): The ID of the reminder.

        Returns:
            Reminder | None: The reminder if found, None otherwise.
        """
        cursor = self.database.cursor()
        cursor.execute("SELECT * FROM reminders WHERE id = ?", (str(reminder_id),))
        row = cursor.fetchone()
        if row:
            return self._row_to_reminder(row)
        return None

    def get_by_guild_and_user(
        self: ReminderRepository, guild_id: int, user_id: int
    ) -> list[Reminder]:
        """
        Retrieves all reminders for a specific user in a guild.

        Args:
            guild_id (int): The ID of the guild.
            user_id (int): The ID of the user.

        Returns:
            list[Reminder]: List of reminders for the user in the guild.
        """
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT * FROM reminders WHERE guild_id = ? AND user_id = ? ORDER BY dispatch_time ASC",
            (guild_id, user_id),
        )
        rows = cursor.fetchall()
        return [self._row_to_reminder(row) for row in rows]

    def get_upcoming(self: ReminderRepository, time_limit: int = 300) -> list[Reminder]:
        """
        Retrieves all upcoming reminders within the time limit.

        Args:
            time_limit (int): The time limit in seconds.

        Returns:
            list[Reminder]: List of upcoming reminders.
        """
        current_time = int(time.time())
        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT * FROM reminders 
            WHERE dispatch_time <= ? AND dispatch_time >= ?
            ORDER BY dispatch_time ASC
            """,
            (current_time + time_limit, current_time),
        )
        rows = cursor.fetchall()
        return [self._row_to_reminder(row) for row in rows]

    def remove(self: ReminderRepository, reminder_id: uuid.UUID) -> None:
        """
        Removes a reminder from the repository.

        Args:
            reminder_id (uuid.UUID): The ID of the reminder to remove.
        """
        cursor = self.database.cursor()
        cursor.execute("DELETE FROM reminders WHERE id = ?", (str(reminder_id),))
        self.database.commit()

    def _row_to_reminder(self: ReminderRepository, row: tuple) -> Reminder:
        """
        Converts a database row to a Reminder instance.

        Args:
            row (tuple): The database row.

        Returns:
            Reminder: The Reminder instance.
        """
        return Reminder(
            uuid.UUID(row[0]),
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
        )

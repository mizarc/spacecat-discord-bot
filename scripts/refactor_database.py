import sqlite3


def main():
    db = sqlite3.connect('../data/spacecat.db')
    cursor = db.cursor()

    # Check if database has already been refactored by checking if column name
    # is server_id or serverid
    cursor.execute(
        'SELECT * FROM group_permissions WHERE 1=0')
    identifier = cursor.description[0][0]
    
    if identifier == 'server_id':
        print("Database has already been refactored.")
        return

    # Server settings
    cursor.execute('ALTER TABLE command_aliases RENAME TO command_alias')
    print("Command alias db transfer complete.")

    # Group permissions
    cursor.execute(
        'ALTER TABLE group_permissions RENAME TO group_permissions_temp')
    cursor.execute(
        'CREATE TABLE group_permission'
        '(server_id INTEGER, group_id INTEGER, permission TEXT)')
    cursor.execute(
        'INSERT INTO group_permission(server_id, group_id, permission)'
        'SELECT serverid, groupid, perm FROM group_permissions_temp')
    cursor.execute('DROP TABLE group_permissions_temp')
    print("Group permission db transfer complete.")

    # User permissions
    cursor.execute(
        'ALTER TABLE user_permissions RENAME TO user_permissions_temp')
    cursor.execute(
        'CREATE TABLE user_permission'
        '(server_id INTEGER, user_id INTEGER, permission TEXT)')
    cursor.execute(
        'INSERT INTO user_permission(server_id, user_id, permission)'
        'SELECT serverid, userid, perm FROM user_permissions_temp')
    cursor.execute('DROP TABLE user_permissions_temp')
    print("User permission db transfer complete.")

    # Group parents
    cursor.execute(
        'ALTER TABLE group_parents RENAME TO group_parents_temp')
    cursor.execute(
        'CREATE TABLE group_parent'
        '(server_id INTEGER, parent_group INTEGER, child_group INTEGER)')
    cursor.execute(
        'INSERT INTO group_parent(server_id, parent_group, child_group)'
        'SELECT serverid, parent_group, child_group FROM group_parents_temp')
    cursor.execute('DROP TABLE group_parents_temp')
    print("Group parent db transfer complete.")

    db.commit()
    db.close()
    print("Changes Finalised.")


if __name__ == "__main__":
    main()
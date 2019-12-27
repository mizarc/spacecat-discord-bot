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

    # Group permissions
    cursor.execute(
        'ALTER TABLE group_permissions RENAME TO group_permissions_temp')
    cursor.execute(
        'CREATE TABLE group_permissions'
        '(server_id INTEGER, group_id INTEGER, perm TEXT)')
    cursor.execute(
        'INSERT INTO group_permissions(server_id, group_id, perm)'
        'SELECT serverid, groupid, perm FROM group_permissions_temp')
    cursor.execute('DROP TABLE group_permissions_temp')
    print("Group permissions db transfer complete.")

    # User permissions
    cursor.execute(
        'ALTER TABLE user_permissions RENAME TO user_permissions_temp')
    cursor.execute(
        'CREATE TABLE user_permissions'
        '(server_id INTEGER, user_id INTEGER, perm TEXT)')
    cursor.execute(
        'INSERT INTO user_permissions(server_id, user_id, perm)'
        'SELECT serverid, userid, perm FROM user_permissions_temp')
    cursor.execute('DROP TABLE user_permissions_temp')
    print("User permissions db transfer complete.")

    # Group parents
    cursor.execute(
        'ALTER TABLE group_parents RENAME TO group_parents_temp')
    cursor.execute(
        'CREATE TABLE group_parents'
        '(server_id INTEGER, parent_group INTEGER, child_group INTEGER)')
    cursor.execute(
        'INSERT INTO group_parents(server_id, parent_group, child_group)'
        'SELECT serverid, parent_group, child_group FROM group_parents_temp')
    cursor.execute('DROP TABLE group_parents_temp')
    print("Group parents db transfer complete.")

    db.commit()
    db.close()
    print("Changes Finalised.")


if __name__ == "__main__":
    main()
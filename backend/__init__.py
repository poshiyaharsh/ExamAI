from django.db.backends.mysql.features import DatabaseFeatures

# Bypass strict MariaDB >= 10.5 check to allow running on XAMPP MariaDB 10.4.x with Django 5.2
DatabaseFeatures.minimum_database_version = property(
    lambda self: (10, 4) if self.connection.mysql_is_mariadb else (8, 0, 11)
)

# MariaDB < 10.5 does not support INSERT ... RETURNING syntax
DatabaseFeatures.can_return_columns_from_insert = property(
    lambda self: self.connection.mysql_is_mariadb and self.connection.mysql_version >= (10, 5, 0)
)
DatabaseFeatures.can_return_rows_from_bulk_insert = property(
    lambda self: self.connection.mysql_is_mariadb and self.connection.mysql_version >= (10, 5, 0)
)

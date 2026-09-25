ALTER TABLE dbo.users
ADD CONSTRAINT CK_users_auth_version CHECK (auth_version >= 0);

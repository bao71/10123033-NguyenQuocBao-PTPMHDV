ALTER TABLE dbo.users
ADD auth_version INT NOT NULL
    CONSTRAINT DF_users_auth_version DEFAULT 0;

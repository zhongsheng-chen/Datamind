DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'status') THEN
        CREATE TYPE status AS ENUM ('active', 'inactive', 'pending', 'deprecated');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'stage') THEN
        CREATE TYPE stage AS ENUM ('underwriting', 'disbursement');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'decision') THEN
        CREATE TYPE decision AS ENUM ('approved', 'rejected', 'warning', 'manual_review');
    END IF;
END $$;
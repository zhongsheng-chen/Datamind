DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'model_status') THEN
        CREATE TYPE model_status AS ENUM (
            'pending',    -- 待注册或待激活
            'active',     -- 已上线，可用
            'inactive',   -- 暂停使用
            'archived'    -- 已归档，历史记录
        );
    END IF;
END$$;

CREATE OR REPLACE FUNCTION fn_model_registry_history()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO model_registry_history
    (model_id, uuid, model_name, model_type, model_path, version, framework, hash, tag, status,
     business_name, changed_by, changed_at, operation_type)
    VALUES
    (NEW.id, NEW.uuid, NEW.model_name, NEW.model_type, NEW.model_path, NEW.version, NEW.framework, NEW.hash,
     NEW.tag, NEW.status, NEW.business_name, current_user, CURRENT_TIMESTAMP,
     TG_OP::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_model_registry_history
AFTER INSERT OR UPDATE ON model_registry
FOR EACH ROW
EXECUTE FUNCTION fn_model_registry_history();
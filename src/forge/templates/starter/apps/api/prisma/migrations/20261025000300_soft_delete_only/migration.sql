CREATE FUNCTION soft_delete_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Records are soft deleted. Set the deleted timestamp instead.';
END;
$$;

CREATE TRIGGER soft_delete_only
BEFORE DELETE ON "Project"
FOR EACH ROW EXECUTE FUNCTION soft_delete_only();

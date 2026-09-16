-- Apply after add_cadu_family.sql. Existing installations used a check that
-- predates the Skills surface; changing it is additive and rewrites no rows.
ALTER TABLE cadu_family_conversation_context
    DROP CONSTRAINT IF EXISTS cadu_family_conversation_context_profile_check;

ALTER TABLE cadu_family_conversation_context
    ADD CONSTRAINT cadu_family_conversation_context_profile_check
    CHECK (profile IN ('workspace', 'planner', 'connect', 'skills'));

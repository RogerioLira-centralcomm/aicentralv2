-- User-owned launch links in the Workspace dock. The metadata stores only
-- the public URL and display title; no OAuth credentials or fetched content.
ALTER TABLE cadu_workspace_dock_shortcuts
    DROP CONSTRAINT IF EXISTS cadu_workspace_dock_shortcuts_shortcut_type_check;
ALTER TABLE cadu_workspace_dock_shortcuts
    ADD CONSTRAINT cadu_workspace_dock_shortcuts_shortcut_type_check
    CHECK (shortcut_type IN ('brand', 'project', 'conversation', 'artifact', 'resource', 'plan', 'image', 'file', 'external'));
